/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise the actual board policy headers without accessing hardware. */
#include <assert.h>
#include <stdio.h>
#include "erhai_cell_envelope.h"
#include "erhai_buck.h"
#include "erhai_svooc_lcf.h"

static void curves(void)
{
	const struct erhai_charge_curve *curve;
	unsigned int s, t, i;
	int soc, temp;

	assert(!erhai_cell_entry(-1, 250, 4000));
	assert(!erhai_cell_entry(101, 250, 4000));
	assert(!erhai_cell_entry(50, -1, 4000));
	assert(!erhai_cell_entry(50, 510, 4000));
	assert(!erhai_cell_entry(50, 250, 0));
	for (soc = 0; soc <= 100; soc++) {
		for (temp = 0; temp < 510; temp++) {
			assert(erhai_cell_entry(soc, temp, 3500));
			assert(!erhai_cell_entry(soc, temp, erhai_cell_cv(temp)));
		}
	}
	/* A high-SOC attachment must retain an admissible final SOC row. */
	curve = erhai_curve_select(svooc_curves, 99, 300);
	assert(curve == &svooc_curves[5][4]);
	assert(erhai_curve_select(svooc_curves, 55, 300) == &svooc_curves[2][4]);
	assert(erhai_curve_select(svooc_curves, 56, 300) == &svooc_curves[3][4]);
	for (s = 0; s < ARRAY_SIZE(svooc_curves); s++) {
		for (t = 0; t < ARRAY_SIZE(svooc_curves[0]); t++) {
			curve = &svooc_curves[s][t];
			assert(curve->count > 0);
			assert(curve->steps[curve->count - 1].last);
			for (i = 0; i < curve->count; i++) {
				assert(curve->steps[i].ma > 0 && curve->steps[i].ma <= 6100);
				if (i) {
					assert(curve->steps[i].mv >= curve->steps[i - 1].mv);
					assert(curve->steps[i].ma <= curve->steps[i - 1].ma);
				}
			}
		}
	}
}

static void low_current_full(void)
{
	struct erhai_svooc_lcf full;
	unsigned int i;

	erhai_svooc_lcf_start(&full, 250, 0);
	/* A repeated read inside the sample period must not count as full. */
	for (i = 0; i < 20; i++)
		assert(!erhai_svooc_lcf_update(&full, 250, 4545, 1000, 999));
	for (i = 1; i <= 6; i++)
		assert(!erhai_svooc_lcf_update(&full, 250, 4545, 1000, i * 1000));
	assert(erhai_svooc_lcf_update(&full, 250, 4545, 1000, 7000));
	erhai_svooc_lcf_start(&full, 250, 0);
	for (i = 1; i <= 20; i++)
		assert(!erhai_svooc_lcf_update(&full, 250, 4400, 1000, i * 1000));
	erhai_svooc_lcf_start(&full, 250, 0);
	for (i = 1; i <= 20; i++)
		assert(!erhai_svooc_lcf_update(&full, 250, 4545, 4000, i * 1000));
}

static void buck_protection_and_recharge(void)
{
	struct erhai_buck b = { 0 };
	struct erhai_buck_sample sample = {
		.mv = 4450, .ma = 500, .temp = 300, .soc = 99, .qualified = true,
	};
	unsigned int i;

	erhai_buck_start(&b, 0);
	for (i = 0; i < 6; i++)
		erhai_buck_update(&b, &sample, i * 4000);
	assert(b.phase == ERHAI_BUCK_FULL && b.disable);
	/* Full is stable until enough low-voltage observations request recharge. */
	sample.mv = 4300;
	for (i = 6; i < 11; i++) {
		erhai_buck_update(&b, &sample, i * 4000);
		assert(b.phase == ERHAI_BUCK_FULL);
	}
	erhai_buck_update(&b, &sample, 44000);
	assert(b.phase == ERHAI_BUCK_NORMAL && b.recharged && !b.disable);
	sample.mv = 4600;
	erhai_buck_update(&b, &sample, 48000);
	assert(b.over_voltage && b.disable);
	sample.mv = 4450;
	erhai_buck_update(&b, &sample, 52000);
	assert(b.over_voltage && b.disable);
	sample.mv = 4399;
	erhai_buck_update(&b, &sample, 56000);
	assert(!b.over_voltage && !b.disable);
	sample.temp = 530;
	erhai_buck_update(&b, &sample, 60000);
	assert(b.disable);
	sample.temp = 450;
	sample.mv = 4400;
	erhai_buck_update(&b, &sample, 64000);
	assert(b.disable);
	sample.qualified = false;
	sample.temp = 250;
	sample.mv = 3800;
	erhai_buck_update(&b, &sample, 68000);
	assert(b.fv_mv <= 3980 && b.fcc_ma == 500);
}

int main(void)
{
	curves();
	low_current_full();
	buck_protection_and_recharge();
	puts("charging curves, low-current full, protection and recharge: passed");
	return 0;
}
