#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define ATH12K_FW_DIR "ath12k"
#define ATH12K_HW_WCN7860_HW20 1
struct params { struct { const char *dir; } fw; };
struct device { void *of_node; };
struct ath12k_base { int hw_rev; struct params *hw_params; struct device *dev; };
static bool opd2413;
static const char *override;
static bool of_machine_is_compatible(const char *name)
{
    return opd2413 && strcmp(name, "oneplus,opd2413") == 0;
}
static int of_property_read_string(void *node, const char *property, const char **value)
{
    (void)node;
    assert(strcmp(property, "firmware-name") == 0);
    *value = override;
    return override ? 0 : -1;
}
#include "fw-path.inc"

int main(void)
{
    struct params params = { .fw.dir = "WCN7860/hw2.0" };
    struct device dev = {0};
    struct ath12k_base ab = { ATH12K_HW_WCN7860_HW20, &params, &dev };
    const char *files[] = { "amss.bin", "aux_ucode.bin", "board-2.bin",
                           "board.bin", "m3.bin", "qdss.cfg", "regdb.bin" };
    char actual[100], expected[100];
    opd2413 = true;
    override = "unrelated-override";
    for (size_t i = 0; i < sizeof(files) / sizeof(files[0]); i++) {
        ath12k_core_create_firmware_path(&ab, files[i], actual, sizeof(actual));
        snprintf(expected, sizeof(expected), "ath12k/WCN7860/hw2.0/oneplus/opd2413/%s", files[i]);
        assert(strcmp(actual, expected) == 0);
    }
    /* Other machines and other chip revisions retain upstream routing. */
    opd2413 = false;
    ath12k_core_create_firmware_path(&ab, "board.bin", actual, sizeof(actual));
    assert(strcmp(actual, "ath12k/WCN7860/hw2.0/board.bin") == 0);
    ath12k_core_create_firmware_path(&ab, "amss.bin", actual, sizeof(actual));
    assert(strcmp(actual, "ath12k/WCN7860/hw2.0/unrelated-override/amss.bin") == 0);
    opd2413 = true;
    ab.hw_rev = 2;
    override = NULL;
    ath12k_core_create_firmware_path(&ab, "amss.bin", actual, sizeof(actual));
    assert(strcmp(actual, "ath12k/WCN7860/hw2.0/amss.bin") == 0);
    puts("OPD2413 firmware routing: OEM set, BDF fallback and scope checks passed");
}
