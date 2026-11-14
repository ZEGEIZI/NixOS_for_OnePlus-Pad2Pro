#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
struct firmware { size_t size; const u8 *data; };
struct cps8601 { void *dev; void *int_gpiod; int prog_lock; };
#define CPS8601_FW_RETRIES 5
#define CPS8601_FW_BIN_VER_OFF 0xc4
#define CPS8601_REG_FW_VER 2
static bool fw_force;
static unsigned int fw_project_id = 24926;
static int requests, loader_warnings, infos, warnings, released, updates, gpio_writes, locks;
static int response, transient_failures, update_result;
static u16 running_version;
static u8 image_data[0xc8];
static struct firmware image;
#define dev_info(...) (++infos)
#define dev_warn(...) (++warnings)
#define dev_dbg(...) ((void)0)
static void release_firmware(const struct firmware *fw) { if (fw) ++released; }
static int fetch(const struct firmware **fw, const char *path, void *dev)
{
    (void)dev;
    assert(strcmp(path, "wireless_pen/24926/cps8601_firmware.bin") == 0);
    ++requests;
    if (requests <= transient_failures) { *fw = NULL; return -EAGAIN; }
    *fw = response ? NULL : &image;
    return response;
}
static int firmware_request_nowarn(const struct firmware **fw, const char *path, void *dev)
{ return fetch(fw, path, dev); }
static int request_firmware(const struct firmware **fw, const char *path, void *dev)
{ int ret = fetch(fw, path, dev); if (ret) ++loader_warnings; return ret; }
static int cps8601_read16(struct cps8601 *chip, unsigned int reg, u16 *value)
{ (void)chip; assert(reg == CPS8601_REG_FW_VER); *value = running_version; return 0; }
static int gpiod_direction_output(void *gpio, int value)
{ (void)gpio; assert(value == 1); ++gpio_writes; return 0; }
static int gpiod_direction_input(void *gpio)
{ (void)gpio; ++gpio_writes; return 0; }
static void msleep(unsigned int ms) { assert(ms == 50); }
static void mutex_lock(int *lock) { (void)lock; ++locks; }
static void mutex_unlock(int *lock) { (void)lock; --locks; }
static int cps8601_do_fw_update(struct cps8601 *chip, const u8 *data, size_t size)
{ (void)chip; assert(locks == 1 && data == image.data && size == image.size); ++updates; return update_result; }

#include "fw-check.inc"

static void reset(void)
{
    requests = loader_warnings = infos = warnings = released = updates = gpio_writes = locks = 0;
    response = -ENOENT; transient_failures = update_result = 0; fw_force = false;
    running_version = 0x011e;
    memset(image_data, 0, sizeof(image_data));
    image_data[0xc4] = 1; image_data[0xc5] = 0x1e;
    image.size = sizeof(image_data); image.data = image_data;
}
int main(void)
{
    struct cps8601 chip = {0};
    reset(); cps8601_fw_update_check(&chip);
    assert(requests == 5 && loader_warnings == 0 && infos == 1 && warnings == 0);
    assert(updates == 0 && gpio_writes == 0 && released == 0);

    reset(); response = -EIO; cps8601_fw_update_check(&chip);
    assert(requests == 5 && warnings == 1 && infos == 0 && updates == 0 && gpio_writes == 0);

    reset(); response = 0; image.size = 0xc5; cps8601_fw_update_check(&chip);
    assert(warnings == 1 && updates == 0 && gpio_writes == 0 && released == 1);

    reset(); response = 0; cps8601_fw_update_check(&chip);
    assert(updates == 0 && warnings == 0 && gpio_writes == 2 && released == 1);

    reset(); response = 0; image_data[0xc5] = 0x1f; cps8601_fw_update_check(&chip);
    assert(updates == 1 && locks == 0 && warnings == 0 && gpio_writes == 2 && released == 1);

    reset(); response = 0; fw_force = true; cps8601_fw_update_check(&chip);
    assert(updates == 1 && locks == 0 && released == 1);

    reset(); response = 0; image_data[0xc5] = 0x1f; update_result = -EIO; cps8601_fw_update_check(&chip);
    assert(updates == 1 && warnings == 1 && locks == 0 && released == 1);

    reset(); response = 0; transient_failures = 2; cps8601_fw_update_check(&chip);
    assert(requests == 3 && updates == 0 && warnings == 0 && released == 1);
    puts("CPS8601: 8 firmware failure/update scenarios passed (mock hardware only)");
    return 0;
}
