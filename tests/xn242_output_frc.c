/* SPDX-License-Identifier: MIT
 * Exercise the actual compositor GLSL with its intermediate framebuffer.
 * The FP16 negative control catches precision lost before the FRC shader.
 * This verifies digital output, not DSC reconstruction or panel luminance.
 */
#define EGL_EGLEXT_PROTOTYPES
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef GL_RGBA16_EXT
#define GL_RGBA16_EXT 0x805B
#endif

enum { WIDTH = 3392, HEIGHT = 20, MAX_LEVEL = 4080 };

static GLuint shader(GLenum type, const char *source)
{
    GLuint id = glCreateShader(type);
    GLint ok;
    glShaderSource(id, 1, &source, NULL);
    glCompileShader(id);
    glGetShaderiv(id, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[4096];
        glGetShaderInfoLog(id, sizeof(log), NULL, log);
        fprintf(stderr, "%s\n", log);
        exit(1);
    }
    return id;
}

static GLuint program(const char *fragment)
{
    const char *vertex = "#version 300 es\n"
        "void main(){vec2 p=vec2(gl_VertexID==1?3.0:-1.0,"
        "gl_VertexID==2?3.0:-1.0);gl_Position=vec4(p,0,1);}";
    GLuint p = glCreateProgram();
    GLuint vs = shader(GL_VERTEX_SHADER, vertex);
    GLuint fs = shader(GL_FRAGMENT_SHADER, fragment);
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    GLint linked;
    glGetProgramiv(p, GL_LINK_STATUS, &linked);
    assert(linked);
    glDeleteShader(vs);
    glDeleteShader(fs);
    return p;
}

static GLuint framebuffer(GLenum format, GLuint *texture)
{
    GLuint fbo;
    glGenTextures(1, texture);
    glBindTexture(GL_TEXTURE_2D, *texture);
    glTexStorage2D(GL_TEXTURE_2D, 1, format, WIDTH, HEIGHT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           GL_TEXTURE_2D, *texture, 0);
    assert(glGetError() == GL_NO_ERROR);
    assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    return fbo;
}

static int level_at(int x, int y)
{
    int value = x / 4 + (y / 4) * (WIDTH / 4);
    return value > MAX_LEVEL ? MAX_LEVEL : value;
}

static unsigned check_format(GLenum format, const char *name,
                              GLuint input_program, GLuint frc_program,
                              GLuint output_fbo)
{
    GLuint input_texture;
    GLuint input_fbo = framebuffer(format, &input_texture);
    glUseProgram(input_program);
    glDrawArrays(GL_TRIANGLES, 0, 3);

    glBindFramebuffer(GL_FRAMEBUFFER, output_fbo);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, input_texture);
    glUseProgram(frc_program);
    glUniform1i(glGetUniformLocation(frc_program, "input_texture"), 0);
    GLint phase = glGetUniformLocation(frc_program, "output_frc_phase");
    assert(phase >= 0);
    unsigned *pixel = calloc(WIDTH * HEIGHT, sizeof(*pixel));
    unsigned short *sum = calloc(WIDTH * HEIGHT, sizeof(*sum));
    assert(pixel && sum);
    unsigned mismatches = 0;
    for (int frame = 0; frame < 16; ++frame) {
        glUniform1f(phase, (frame * 5) % 16);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glReadPixels(0, 0, WIDTH, HEIGHT, GL_RGBA,
                     GL_UNSIGNED_INT_2_10_10_10_REV, pixel);
        assert(glGetError() == GL_NO_ERROR);
        for (int y = 0; y < HEIGHT; y += 4) {
            for (int x = 0; x < WIDTH; x += 4) {
                unsigned total[3] = {0};
                int value = level_at(x, y);
                for (int j = 0; j < 4; ++j) {
                    for (int i = 0; i < 4; ++i) {
                        int idx = (y + j) * WIDTH + x + i;
                        for (int c = 0; c < 3; ++c) {
                            unsigned code = (pixel[idx] >> (10 * c)) & 1023u;
                            assert((code & 3) == 0);
                            total[c] += code / 4;
                        }
                        sum[idx] += (pixel[idx] & 1023u) / 4;
                    }
                }
                if (total[0] != (unsigned)value ||
                    total[1] != (unsigned)(MAX_LEVEL - value) || total[2] != 0)
                    ++mismatches;
            }
        }
    }
    for (int y = 0; y < HEIGHT; ++y)
        for (int x = 0; x < WIDTH; ++x)
            if (sum[y * WIDTH + x] != level_at(x, y))
                ++mismatches;
    printf("%s composition → FRC → XR30: %u spatial/temporal mismatches\n",
           name, mismatches);
    free(pixel);
    free(sum);
    glDeleteFramebuffers(1, &input_fbo);
    glDeleteTextures(1, &input_texture);
    return mismatches;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    FILE *file = fopen(argv[1], "r");
    assert(file);
    char source[8192];
    size_t length = fread(source, 1, sizeof(source) - 1, file);
    assert(feof(file));
    fclose(file);
    source[length] = 0;
    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA,
                                               EGL_DEFAULT_DISPLAY, NULL);
    assert(display != EGL_NO_DISPLAY && eglInitialize(display, NULL, NULL));
    assert(eglBindAPI(EGL_OPENGL_ES_API));
    const EGLint attrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE};
    const EGLint ctx_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    const EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLConfig config;
    EGLint configs;
    assert(eglChooseConfig(display, attrs, &config, 1, &configs) && configs == 1);
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, ctx_attrs);
    EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attrs);
    assert(context != EGL_NO_CONTEXT && surface != EGL_NO_SURFACE);
    assert(eglMakeCurrent(display, surface, surface, context));
    printf("Renderer: %s\n", glGetString(GL_RENDERER));
    GLuint frc_program = program(source);
    GLuint input_program = program("#version 300 es\nprecision highp float;\n"
        "out vec4 frag;\nvoid main(){vec2 tile=floor(gl_FragCoord.xy/4.0);"
        "float v=min(tile.x+848.0*tile.y,4080.0)/4080.0;"
        "frag=vec4(v,1.0-v,0.0,1.0);}");
    GLuint output_texture;
    GLuint output_fbo = framebuffer(GL_RGB10_A2, &output_texture);
    glViewport(0, 0, WIDTH, HEIGHT);
    glDisable(GL_DITHER);
    assert(check_format(GL_RGBA16F, "FP16 negative control", input_program,
                         frc_program, output_fbo) > 0);
    assert(check_format(GL_RGBA16_EXT, "UNORM16", input_program,
                         frc_program, output_fbo) == 0);
    assert(check_format(GL_RGBA32F, "FP32 fallback", input_program,
                         frc_program, output_fbo) == 0);
    puts("4081 target levels, 16 phases, RGB channels and intermediate precision passed.");
    eglTerminate(display);
    return 0;
}
