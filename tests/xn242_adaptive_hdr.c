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
#include <math.h>
#include <string.h>

#ifndef GL_RGBA16_EXT
#define GL_RGBA16_EXT 0x805B
#endif



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

static char *read_source(const char *path)
{
    FILE *file = fopen(path, "rb");
    assert(file);
    char *source = calloc(16384, 1);
    assert(source);
    size_t length = fread(source, 1, 16383, file);
    assert(feof(file) && length);
    fclose(file);
    return source;
}

static GLuint framebuffer(int width, int height, GLenum format, GLuint *texture)
{
    GLuint fbo;
    glGenTextures(1, texture);
    glBindTexture(GL_TEXTURE_2D, *texture);
    glTexStorage2D(GL_TEXTURE_2D, 1, format, width, height);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, *texture, 0);
    assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    return fbo;
}

static void check_reduction(GLuint reduction, int width, int height)
{
    GLuint texture, fbo = framebuffer(width, height, GL_RGBA8, &texture);
    unsigned char *black = calloc((size_t)width * height, 4);
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, black);
    free(black);
    int positions[][2] = {{0, 0}, {width-1, 0}, {0, height-1},
        {width-1, height-1}, {width/2, height/2}, {3, 4}, {17, 31}};
    for (unsigned test = 0; test < sizeof(positions)/sizeof(positions[0]); test++) {
        unsigned char pixel[] = {17, 113, 251, 255};
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexSubImage2D(GL_TEXTURE_2D, 0, positions[test][0], positions[test][1], 1, 1,
                        GL_RGBA, GL_UNSIGNED_BYTE, pixel);
        GLuint previous = texture, levels[12], buffers[12];
        int w = width, h = height, n = 0;
        while (w > 1 || h > 1) {
            int nw = (w + 3) / 4, nh = (h + 3) / 4;
            buffers[n] = framebuffer(nw, nh, GL_RGBA8, &levels[n]);
            glViewport(0, 0, nw, nh);
            glBindTexture(GL_TEXTURE_2D, previous);
            glUseProgram(reduction);
            glUniform1i(glGetUniformLocation(reduction, "cogl_sampler0"), 0);
            glUniform4f(glGetUniformLocation(reduction, "xn242_size"), w, h, nw, nh);
            glDrawArrays(GL_TRIANGLES, 0, 3);
            previous = levels[n++]; w = nw; h = nh;
        }
        unsigned char result[4];
        glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, result);
        assert(glGetError() == GL_NO_ERROR);
        assert(result[0] == 17 && result[1] == 113 && result[2] == 251);
        glDeleteTextures(n, levels);
        glDeleteFramebuffers(n, buffers);
        glBindTexture(GL_TEXTURE_2D, texture);
        memset(pixel, 0, 4);
        glTexSubImage2D(GL_TEXTURE_2D, 0, positions[test][0], positions[test][1], 1, 1,
                        GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    }
    glDeleteTextures(1, &texture); glDeleteFramebuffers(1, &fbo);
    printf("Exact maximum: %dx%d, one-pixel highlights at corners, center and tile boundaries passed\n", width, height);
}

static void check_compensation(GLuint compensation)
{
    GLuint texture, input = framebuffer(1, 1, GL_RGBA32F, &texture);
    GLuint output_texture, output = framebuffer(1, 1, GL_RGBA32F, &output_texture);
    glUseProgram(compensation);
    glUniform1i(glGetUniformLocation(compensation, "cogl_sampler0"), 0);
    glViewport(0, 0, 1, 1);
    double whites[] = {2.03, 7.5, 20, 80, 203, 426.3};
    double max_error = 0;
    for (unsigned i = 0; i < sizeof(whites)/sizeof(whites[0]); i++) {
        double white = whites[i];
        float pixel[] = {pow(white/561.5, 1/2.2), pow(white/561.5, 1/2.2), pow(white/561.5, 1/2.2), 1};
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 1, 1, GL_RGBA, GL_FLOAT, pixel);
        for (double available = white * 1.04; available <= 561.5; available *= 1.031) {
            glBindFramebuffer(GL_FRAMEBUFFER, output);
            glUniform2f(glGetUniformLocation(compensation, "xn242_backlight"), available, white);
            glDrawArrays(GL_TRIANGLES, 0, 3);
            float result[4];
            glReadPixels(0, 0, 1, 1, GL_RGBA, GL_FLOAT, result);
            double error = fabs(pow(result[0], 2.2)*available - white);
            max_error = fmax(max_error, error);
            assert(error < 0.003);
            assert(fabs(result[0]-result[1]) < 1e-6 && result[3] == 1);
        }
    }
    double last = 0;
    for (int nits = 0; nits <= 562; nits++) {
        float pixel[] = {pow(nits/561.5, 1/2.2), pow(nits/561.5, 1/2.2), pow(nits/561.5, 1/2.2), 1};
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 1, 1, GL_RGBA, GL_FLOAT, pixel);
        glUniform2f(glGetUniformLocation(compensation, "xn242_backlight"), 220, 203);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        float result[4];
        glReadPixels(0, 0, 1, 1, GL_RGBA, GL_FLOAT, result);
        assert(result[0] >= last - 1e-6 && result[0] <= 1.000001);
        last = result[0];
    }
    assert(glGetError() == GL_NO_ERROR);
    printf("Actual compensation shader: stable SDR reference (max error %.6f estimated nit), monotonic ramp shoulder passed\n", max_error);
    glDeleteTextures(1, &texture); glDeleteTextures(1, &output_texture);
    glDeleteFramebuffers(1, &input); glDeleteFramebuffers(1, &output);
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    assert(display != EGL_NO_DISPLAY && eglInitialize(display, NULL, NULL));
    assert(eglBindAPI(EGL_OPENGL_ES_API));
    const EGLint attrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT, EGL_NONE};
    const EGLint ctx_attrs[] = {EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE};
    const EGLint surface_attrs[] = {EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
    EGLConfig config; EGLint configs;
    assert(eglChooseConfig(display, attrs, &config, 1, &configs) && configs == 1);
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, ctx_attrs);
    EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attrs);
    assert(context != EGL_NO_CONTEXT && surface != EGL_NO_SURFACE);
    assert(eglMakeCurrent(display, surface, surface, context));
    printf("Renderer: %s\n", glGetString(GL_RENDERER));
    glDisable(GL_DITHER);
    char *reduction_source = read_source(argv[1]), *compensation_source = read_source(argv[2]);
    GLuint reduction = program(reduction_source), compensation = program(compensation_source);
    check_reduction(reduction, 3392, 2400);
    check_reduction(reduction, 257, 129);
    check_compensation(compensation);
    free(reduction_source); free(compensation_source);
    eglTerminate(display);
    return 0;
}
