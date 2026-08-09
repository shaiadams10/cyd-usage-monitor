#ifndef MASCOT_IMG_H
#define MASCOT_IMG_H

#include <lvgl.h>

// 24x24 Pixel Art Red Robot / Claw Mascot Bitmap (16-bit RGB565)
// Color map: 0x0000 = Transparent/Black, 0xF248 = Coral Red, 0xFFFF = White, 0x39E9 = Dark Grey

#define _ 0x0000
#define R 0xF248 // Red (#f43f5e)
#define W 0xFFFF // White (#ffffff)
#define D 0x2104 // Dark (#27272a)
#define C 0x38BF // Cyan (#38bdf8)

static const uint16_t mascot_map[24 * 24] = {
    _,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,
    _,_,R,R,_,_,_,_,_,_,_,_,_,_,_,_,_,_,R,R,_,_,_,_,
    _,R,R,R,R,_,_,_,_,_,_,_,_,_,_,_,_,R,R,R,R,_,_,_,
    _,R,R,_,R,R,_,_,_,_,_,_,_,_,_,_,R,R,_,R,R,_,_,_,
    _,_,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,_,
    _,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,
    _,_,R,R,R,W,W,R,R,R,R,R,R,R,R,W,W,R,R,R,_,_,_,_,
    _,_,R,R,R,W,C,R,R,R,R,R,R,R,R,W,C,R,R,R,_,_,_,_,
    _,_,R,R,R,W,W,R,R,R,R,R,R,R,R,W,W,R,R,R,_,_,_,_,
    _,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,
    _,_,R,R,R,R,R,R,W,W,W,W,W,W,R,R,R,R,R,R,_,_,_,_,
    _,_,R,R,R,R,R,R,D,D,D,D,D,D,R,R,R,R,R,R,_,_,_,_,
    _,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,
    _,_,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,_,
    _,_,_,_,_,_,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,_,_,_,
    _,_,_,_,_,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,_,_,
    _,_,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,_,
    _,_,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,_,
    _,_,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,R,_,_,_,_,
    _,_,R,R,_,_,R,R,R,R,R,R,R,R,R,R,_,_,R,R,_,_,_,_,
    _,_,R,R,_,_,R,R,R,R,R,R,R,R,R,R,_,_,R,R,_,_,_,_,
    _,_,_,_,_,_,R,R,R,_,_,_,_,R,R,R,_,_,_,_,_,_,_,_,
    _,_,_,_,_,_,R,R,R,_,_,_,_,R,R,R,_,_,_,_,_,_,_,_,
    _,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_
};

#undef _
#undef R
#undef W
#undef D
#undef C

static const lv_img_dsc_t mascot_img = {
    .header = {
        .cf = LV_IMG_CF_TRUE_COLOR,
        .always_zero = 0,
        .reserved = 0,
        .w = 24,
        .h = 24,
    },
    .data_size = 24 * 24 * 2,
    .data = (const uint8_t *)mascot_map,
};

#endif // MASCOT_IMG_H
