#ifndef CYD_UI_MOTION_H
#define CYD_UI_MOTION_H

/* Shared LVGL 8 motion for hardware and WASM. All calls stay on the UI task.
 * Fixed storage, small dirty regions, no per-frame allocation or full-screen
 * effects. Hidden screens settle immediately and do not animate in the dark. */
#include <lvgl.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    lv_obj_t *obj;
    int32_t from, target, current;
    uint32_t started, refreshed;
    uint16_t delay;
    bool known, running, shine;
} cyd_motion_value;
static cyd_motion_value cyd_bars[6], cyd_arc, cyd_money[4];
static unsigned cyd_bar_count, cyd_money_count;
static lv_obj_t *cyd_chart;
static lv_chart_series_t *cyd_series;
static int32_t cyd_chart_from[7], cyd_chart_to[7], cyd_chart_now[7];
static uint32_t cyd_chart_started;
static bool cyd_chart_running;
static lv_obj_t *cyd_navigation_target, *cyd_navigation_queued;
static bool cyd_navigation_queued_back;
static bool cyd_navigation_reveal_back;
static uint32_t cyd_navigation_started;
static lv_coord_t cyd_navigation_revealed;
static lv_draw_mask_radius_param_t cyd_navigation_mask;
static int16_t cyd_navigation_mask_id = -1;
static void cyd_motion_show(lv_obj_t *screen, bool back);

static int32_t cyd_ease(uint32_t elapsed, uint32_t duration) {
    if (elapsed >= duration) return 1024;
    int32_t t = 1024 - (int32_t)(elapsed * 1024 / duration);
    return 1024 - (int32_t)(((int64_t)t * t * t) / (1024 * 1024));
}
static bool cyd_visible(lv_obj_t *obj) {
    return obj && lv_obj_is_visible(obj);
}
static void cyd_start_value(cyd_motion_value *v, int32_t target, bool reset) {
    uint32_t now = lv_tick_get();
    bool changed = !v->known || v->target != target || reset;
    if (changed) {
        /* Never blank a populated widget on account or route changes. */
        v->from = !v->known ? 0 : v->current;
        v->current = v->from;
        v->target = target;
        v->started = now;
        v->running = true;
    }
    /* Every fresh value shines; identical cached reads get one sweep / 30s. */
    if (changed || now - v->refreshed >= 30000) {
        v->refreshed = now;
        v->shine = true;
    }
    v->known = true;
}
static void cyd_bar_draw(lv_event_t *event) {
    cyd_motion_value *v = (cyd_motion_value *)lv_event_get_user_data(event);
    uint32_t age = lv_tick_get() - v->refreshed;
    if (!v->shine || age < v->delay || age > v->delay + 850 || v->current <= 0) return;
    lv_area_t area;
    lv_obj_get_coords(v->obj, &area);
    int width = lv_area_get_width(&area) - 4;
    int filled = width * v->current / 1000;
    int head = (int)((age - v->delay) * (width + 24) / 850) - 24;
    int left = head < 0 ? 0 : head;
    int right = head + 18 > filled ? filled : head + 18;
    if (right <= left) return;
    area.x1 += left + 2;
    area.x2 = area.x1 + right - left - 1;
    area.y1 += 2; area.y2 -= 2;
    lv_draw_rect_dsc_t d;
    lv_draw_rect_dsc_init(&d);
    d.bg_color = lv_color_white(); d.bg_opa = LV_OPA_30; d.radius = 3;
    lv_draw_rect(lv_event_get_draw_ctx(event), &d, &area);
}
static void cyd_motion_bar_init(lv_obj_t *bar, uint16_t delay) {
    if (cyd_bar_count >= 6) return;
    cyd_motion_value *v = &cyd_bars[cyd_bar_count++];
    v->obj = bar; v->delay = delay;
    lv_bar_set_range(bar, 0, 1000);
    lv_bar_set_value(bar, 0, LV_ANIM_OFF);
    lv_obj_add_event_cb(bar, cyd_bar_draw, LV_EVENT_DRAW_MAIN_END, v);
}
static void cyd_motion_bar(lv_obj_t *bar, int percent, bool reset) {
    percent = percent < 0 ? 0 : percent > 100 ? 100 : percent;
    for (unsigned i = 0; i < cyd_bar_count; ++i)
        if (cyd_bars[i].obj == bar) cyd_start_value(&cyd_bars[i], percent * 10, reset);
}
static void cyd_motion_arc_init(lv_obj_t *arc) {
    cyd_arc.obj = arc;
    lv_arc_set_range(arc, 0, 1000);
}
static void cyd_motion_arc(int percent, bool reset) {
    percent = percent < 0 ? 0 : percent > 100 ? 100 : percent;
    cyd_start_value(&cyd_arc, percent * 10, reset);
}
static void cyd_motion_money_init(lv_obj_t *label, uint16_t delay) {
    if (cyd_money_count >= 4) return;
    cyd_money[cyd_money_count].obj = label;
    cyd_money[cyd_money_count++].delay = delay;
}
static void cyd_motion_money(lv_obj_t *label, const char *text, bool reset) {
    for (unsigned i = 0; i < cyd_money_count; ++i) {
        cyd_motion_value *v = &cyd_money[i];
        if (v->obj != label) continue;
        char *end;
        double amount = text[0] == '$' ? strtod(text + 1, &end) : -1;
        if (text[0] != '$' || end == text + 1 || *end || !(amount >= 0 && amount <= 1000000)) {
            v->running = false; v->known = false;
            lv_label_set_text(label, text);
        } else cyd_start_value(v, (int32_t)(amount * 100 + 0.5), reset);
        return;
    }
}
static void cyd_motion_chart_init(lv_obj_t *chart, lv_chart_series_t *series) {
    cyd_chart = chart; cyd_series = series;
    for (unsigned i = 0; i < 7; ++i) lv_chart_set_value_by_id(chart, series, i, 0);
}
static void cyd_motion_chart(const int *values, bool reset) {
    bool changed = reset;
    for (unsigned i = 0; i < 7; ++i)
        if (cyd_chart_to[i] != values[i]) changed = true;
    if (!changed) return;
    for (unsigned i = 0; i < 7; ++i) {
        cyd_chart_from[i] = reset ? 0 : cyd_chart_now[i];
        cyd_chart_to[i] = values[i] < 0 ? 0 : values[i] > 100 ? 100 : values[i];
    }
    cyd_chart_started = lv_tick_get(); cyd_chart_running = true;
}

/* Small entry offsets leave screen routes and control handlers unchanged. */
static void cyd_translate(void *obj, int32_t value) {
    lv_obj_set_style_translate_y((lv_obj_t *)obj, value, LV_PART_MAIN);
}
static void cyd_motion_enter(lv_obj_t *obj, uint16_t delay) {
    lv_anim_t a; lv_anim_init(&a);
    lv_anim_set_var(&a, obj); lv_anim_set_exec_cb(&a, cyd_translate);
    lv_anim_set_values(&a, 9, 0); lv_anim_set_time(&a, 380);
    lv_anim_set_delay(&a, delay); lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
    lv_anim_start(&a);
}

/* Ambient motion is confined to launcher icon bars and route nodes. */
static lv_obj_t *cyd_equalizer[3], *cyd_nodes[4];
static void cyd_motion_equalizer(lv_obj_t *parent) {
    for (unsigned i = 0; i < 3; ++i) {
        lv_obj_t *bar = lv_obj_create(parent); cyd_equalizer[i] = bar;
        lv_obj_remove_style_all(bar); lv_obj_clear_flag(bar, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_size(bar, 6, 10); lv_obj_set_pos(bar, 17 + 9 * i, 35);
        lv_obj_set_style_bg_color(bar, lv_color_hex(i == 0 ? 0xFBCFE8 : i == 1 ? 0xBAE6FD : 0xFDE68A), 0);
        lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0); lv_obj_set_style_radius(bar, 2, 0);
    }
}
static void cyd_motion_tick(lv_timer_t *timer) {
    (void)timer;
    uint32_t now = lv_tick_get();
    if (!cyd_navigation_target && cyd_navigation_queued) {
        lv_obj_t *next = cyd_navigation_queued;
        bool back = cyd_navigation_queued_back;
        cyd_navigation_queued = NULL;
        cyd_motion_show(next, back);
    }
    /* Spend the frame budget on the route transition, not two screens of
     * moving widgets. Preserve pending motion so it resumes after arrival. */
    if (cyd_navigation_target) {
        lv_coord_t width = lv_disp_get_hor_res(NULL);
        lv_coord_t next = width * cyd_ease(now - cyd_navigation_started, 420) / 1024;
        if (next > cyd_navigation_revealed) {
            lv_area_t strip = {0, 0, 0, (lv_coord_t)(lv_disp_get_ver_res(NULL) - 1)};
            strip.x1 = cyd_navigation_reveal_back ? cyd_navigation_revealed : width - next;
            strip.x2 = cyd_navigation_reveal_back ? next - 1 : width - cyd_navigation_revealed - 1;
            cyd_navigation_revealed = next;
            lv_obj_invalidate_area(cyd_navigation_target, &strip);
        }
        for (unsigned i = 0; i < cyd_bar_count; ++i) {
            if (cyd_bars[i].running) { cyd_bars[i].started = now; cyd_bars[i].from = cyd_bars[i].current; }
            if (cyd_bars[i].shine) cyd_bars[i].refreshed = now;
        }
        if (cyd_arc.running) { cyd_arc.started = now; cyd_arc.from = cyd_arc.current; }
        for (unsigned i = 0; i < cyd_money_count; ++i)
            if (cyd_money[i].running) { cyd_money[i].started = now; cyd_money[i].from = cyd_money[i].current; }
        if (cyd_chart_running) {
            cyd_chart_started = now;
            for (unsigned i = 0; i < 7; ++i) cyd_chart_from[i] = cyd_chart_now[i];
        }
        return;
    }
    for (unsigned i = 0; i < cyd_bar_count + 1 + cyd_money_count; ++i) {
        cyd_motion_value *v = i < cyd_bar_count ? &cyd_bars[i] : i == cyd_bar_count ? &cyd_arc : &cyd_money[i - cyd_bar_count - 1];
        if (!v->obj) continue;
        bool visible = cyd_visible(v->obj);
        if (v->running) {
            uint32_t age = now - v->started;
            int32_t ease = !visible ? 1024 : age < v->delay ? 0 : cyd_ease(age - v->delay, 720);
            v->current = v->from + (int32_t)((int64_t)(v->target - v->from) * ease / 1024);
            if (i < cyd_bar_count) lv_bar_set_value(v->obj, v->current, LV_ANIM_OFF);
            else if (i == cyd_bar_count) lv_arc_set_value(v->obj, v->current);
            else {
                char text[32]; snprintf(text, sizeof(text), "$%ld.%02ld", (long)(v->current / 100), (long)(v->current % 100));
                if (strcmp(lv_label_get_text(v->obj), text)) lv_label_set_text(v->obj, text);
            }
            if (ease == 1024) v->running = false;
        }
        if (i < cyd_bar_count && v->shine) {
            if (!visible || now - v->refreshed > v->delay + 850) v->shine = false;
            if (visible) lv_obj_invalidate(v->obj);
        }
        if (i == cyd_bar_count && v->shine) {
            uint32_t age = now - v->refreshed;
            uint8_t mix = age < 900 && visible ? (uint8_t)((900 - age) * 90 / 900) : 0;
            lv_obj_set_style_arc_color(v->obj, lv_color_mix(lv_color_white(), lv_color_hex(0xA7F3D0), mix), LV_PART_INDICATOR);
            if (!mix) v->shine = false;
        }
    }
    if (cyd_chart_running && cyd_chart) {
        bool done = true;
        for (unsigned i = 0; i < 7; ++i) {
            uint32_t age = now - cyd_chart_started;
            int32_t ease = !cyd_visible(cyd_chart) ? 1024 : age < i * 55 ? 0 : cyd_ease(age - i * 55, 600);
            cyd_chart_now[i] = cyd_chart_from[i] + (cyd_chart_to[i] - cyd_chart_from[i]) * ease / 1024;
            lv_chart_set_value_by_id(cyd_chart, cyd_series, i, cyd_chart_now[i]);
            if (ease != 1024) done = false;
        }
        cyd_chart_running = !done;
    }
    for (unsigned i = 0; i < 3; ++i) if (cyd_visible(cyd_equalizer[i])) {
        uint32_t phase = (now + i * 330) % 1800;
        int h = 7 + (int)(phase < 900 ? phase : 1800 - phase) * 13 / 900;
        lv_obj_set_height(cyd_equalizer[i], h); lv_obj_set_y(cyd_equalizer[i], 45 - h);
    }
    for (unsigned i = 0; i < 4; ++i) if (cyd_visible(cyd_nodes[i])) {
        uint32_t phase = (now + (4 - i) * 240) % 2000;
        lv_opa_t opacity = phase < 500 ? (lv_opa_t)(100 + (500 - phase) * 155 / 500) : 100;
        lv_obj_set_style_bg_opa(cyd_nodes[i], opacity, 0);
    }
}
static void cyd_motion_init(void) { lv_timer_create(cyd_motion_tick, 33, NULL); }

static void cyd_motion_screen_loaded(lv_event_t *event) {
    lv_obj_t *screen = lv_event_get_target(event);
    if (cyd_navigation_target == screen) cyd_navigation_target = NULL;
    for (unsigned i = 0; i < cyd_bar_count; ++i) {
        cyd_motion_value *v = &cyd_bars[i];
        if (v->known && lv_obj_get_screen(v->obj) == screen && cyd_visible(v->obj)) {
            v->refreshed = lv_tick_get(); v->shine = true;
        }
    }
}
static void cyd_motion_show(lv_obj_t *screen, bool back) {
    if (cyd_navigation_target) {
        /* LVGL otherwise snaps the unfinished screen to its end position. */
        cyd_navigation_queued = screen == cyd_navigation_target ? NULL : screen;
        cyd_navigation_queued_back = back;
        return;
    }
    if (lv_scr_act() == screen) return;
    cyd_navigation_target = screen;
    cyd_navigation_started = lv_tick_get();
    cyd_navigation_revealed = 0;
    cyd_navigation_reveal_back = back;
    /* Keep both screens stationary. The dummy transition retains the old
     * screen beneath a draw mask, while only newly revealed strips are dirty.
     * This avoids copying/rendering 480x320 pixels on every slide frame. */
    lv_scr_load_anim(screen, LV_SCR_LOAD_ANIM_NONE, 440, 0, false);
}
static void cyd_motion_reveal_draw(lv_event_t *event) {
    if (lv_event_get_target(event) != cyd_navigation_target) return;
    lv_event_code_t code = lv_event_get_code(event);
    if (code == LV_EVENT_SCREEN_LOAD_START) {
        /* The motion timer may run before LVGL activates the destination.
         * Strips invalidated before activation are discarded by LVGL. */
        cyd_navigation_started = lv_tick_get();
        cyd_navigation_revealed = 0;
    } else if (code == LV_EVENT_COVER_CHECK) {
        const lv_area_t *area = lv_event_get_cover_area(event);
        lv_coord_t width = lv_disp_get_hor_res(NULL);
        bool covered = cyd_navigation_revealed && (cyd_navigation_reveal_back
            ? area->x2 < cyd_navigation_revealed
            : area->x1 >= width - cyd_navigation_revealed);
        /* Newly exposed strips are opaque: let LVGL skip masks and ancestors
         * there. Only areas crossing the reveal edge need the masked path. */
        if (!covered) lv_event_set_cover_res(event, LV_COVER_RES_MASKED);
    } else if (code == LV_EVENT_DRAW_MAIN_BEGIN) {
        lv_coord_t width = lv_disp_get_hor_res(NULL);
        lv_area_t reveal = {0, 0, (lv_coord_t)(width - 1), (lv_coord_t)(lv_disp_get_ver_res(NULL) - 1)};
        if (!cyd_navigation_revealed) reveal.x1 = reveal.x2 = width;
        else if (cyd_navigation_reveal_back) reveal.x2 = cyd_navigation_revealed - 1;
        else reveal.x1 = width - cyd_navigation_revealed;
        lv_draw_mask_radius_init(&cyd_navigation_mask, &reveal, 0, false);
        cyd_navigation_mask_id = lv_draw_mask_add(&cyd_navigation_mask, NULL);
    } else if (code == LV_EVENT_DRAW_POST_END && cyd_navigation_mask_id >= 0) {
        lv_draw_mask_remove_id(cyd_navigation_mask_id);
        cyd_navigation_mask_id = -1;
    }
}
static void cyd_motion_screen_init(lv_obj_t *screen) {
    lv_obj_add_event_cb(screen, cyd_motion_screen_loaded, LV_EVENT_SCREEN_LOADED, NULL);
    lv_obj_add_event_cb(screen, cyd_motion_reveal_draw, LV_EVENT_ALL, NULL);
}
static void cyd_motion_card_init(lv_obj_t *card) {
    /* Full cards remain still on arrival: translating them here caused a
     * second jump after the screen was already fully visible. */
    (void)card;
}

/* Errors must cancel in-flight values before displaying unavailable content. */
static void cyd_motion_openrouter_error(void) {
    cyd_arc.running = cyd_arc.known = false; cyd_arc.current = 0;
    lv_arc_set_value(cyd_arc.obj, 0);
    cyd_chart_running = false;
    for (unsigned i = 0; i < 4; ++i) {
        cyd_money[i].running = cyd_money[i].known = false;
        if (cyd_money[i].obj) lv_label_set_text(cyd_money[i].obj, "--");
    }
    for (unsigned i = 0; i < 7; ++i) {
        cyd_chart_now[i] = cyd_chart_to[i] = 0;
        lv_chart_set_value_by_id(cyd_chart, cyd_series, i, 0);
    }
}
#endif
