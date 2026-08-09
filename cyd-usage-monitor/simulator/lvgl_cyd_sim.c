#include <emscripten/emscripten.h>
#include <lvgl.h>
#include <stdint.h>
#include <stdlib.h>
#include "../src/mascot_img.h"

#define SCREEN_W 320
#define SCREEN_H 240

static lv_color_t buffer[SCREEN_W * 24];
static lv_disp_draw_buf_t draw_buffer;
static lv_obj_t *mascot, *ag_mascot, *header, *plan, *primary_card, *details_card, *error_card, *error_title, *error_detail, *primary_value, *primary_tag, *primary_sub, *primary_warn, *primary_bar, *credits, *server_status;
static lv_obj_t *grid, *gemini_heading, *claude_heading, *g5, *gw, *c5, *cw;

EM_JS(void, canvas_blit, (int x, int y, int width, int height, const uint16_t *pixels), {
  const canvas = Module.canvas;
  const ctx = canvas.getContext('2d', { alpha: false });
  const image = ctx.createImageData(width, height);
  const source = HEAPU16.subarray(pixels >>> 1, (pixels >>> 1) + width * height);
  for (let i = 0; i < source.length; i++) {
    const value = source[i];
    const offset = i * 4;
    image.data[offset] = ((value >> 11) & 31) * 255 / 31;
    image.data[offset + 1] = ((value >> 5) & 63) * 255 / 63;
    image.data[offset + 2] = (value & 31) * 255 / 31;
    image.data[offset + 3] = 255;
  }
  ctx.putImageData(image, x, y);
});

// Export the exact same 24x24 RGB565 mascot bitmaps used by the firmware as
// data URLs for the account badges in the dashboard.  This avoids maintaining
// a second, CSS-drawn provider logo that could drift from the physical CYD.
EM_JS(void, publish_mascot, (int provider, const uint16_t *pixels), {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 24;
  const image = canvas.getContext('2d').createImageData(24, 24);
  const source = HEAPU16.subarray(pixels >>> 1, (pixels >>> 1) + 24 * 24);
  for (let i = 0; i < source.length; i++) {
    const value = source[i], offset = i * 4;
    image.data[offset] = ((value >> 11) & 31) * 255 / 31;
    image.data[offset + 1] = ((value >> 5) & 63) * 255 / 63;
    image.data[offset + 2] = (value & 31) * 255 / 31;
    image.data[offset + 3] = 255;
  }
  canvas.getContext('2d').putImageData(image, 0, 0);
  window.cydProviderMascots = window.cydProviderMascots || {};
  window.cydProviderMascots[provider ? 'antigravity' : 'codex'] = canvas.toDataURL('image/png');
});

EMSCRIPTEN_KEEPALIVE void cyd_publish_provider_mascots(void) {
  publish_mascot(0, (const uint16_t *)mascot_pixel_map);
  publish_mascot(1, (const uint16_t *)antigravity_mascot_pixel_map);
}

static void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *color) {
  const int width = area->x2 - area->x1 + 1;
  const int height = area->y2 - area->y1 + 1;
  canvas_blit(area->x1, area->y1, width, height, (const uint16_t *)color);
  lv_disp_flush_ready(driver);
}

static void style_card(lv_obj_t *card, uint32_t border, int radius) {
  lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(card, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_style_bg_color(card, lv_color_hex(0x18181B), LV_PART_MAIN);
  lv_obj_set_style_border_color(card, lv_color_hex(border), LV_PART_MAIN);
  lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
  lv_obj_set_style_radius(card, radius, LV_PART_MAIN);
  lv_obj_set_style_pad_all(card, 7, LV_PART_MAIN);
}

static lv_obj_t *make_grid_card(lv_obj_t *parent, const char *title, int x, int y, uint32_t color) {
  lv_obj_t *card = lv_obj_create(parent);
  // Keep a two-pixel safety gutter at the canvas edge.  The physical layout
  // is full width, but the browser rasterizer otherwise clips the final
  // Antigravity card border at 320 logical pixels.
  lv_obj_set_size(card, 156, 88);
  lv_obj_set_pos(card, x, y);
  style_card(card, color, 8);
  lv_obj_t *label = lv_label_create(card);
  lv_label_set_text(label, title);
  lv_obj_set_style_text_color(label, lv_color_hex(color), LV_PART_MAIN);
  lv_obj_set_style_text_font(label, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(label, 3, 2);
  return card;
}

static void set_grid_card(lv_obj_t *card, const char *value, const char *sub, uint32_t color) {
  lv_obj_t *value_label = lv_obj_get_child(card, 1);
  lv_obj_t *bar = lv_obj_get_child(card, 2);
  lv_obj_t *sub_label = lv_obj_get_child(card, 3);
  lv_label_set_text(value_label, value);
  lv_obj_set_style_text_color(value_label, lv_color_hex(color), LV_PART_MAIN);
  lv_bar_set_value(bar, atoi(value), LV_ANIM_OFF);
  lv_label_set_text(sub_label, sub);
}

static void finish_grid_card(lv_obj_t *card, uint32_t color) {
  lv_obj_t *value = lv_label_create(card);
  lv_label_set_text(value, "-");
  lv_obj_set_style_text_font(value, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_align(value, LV_ALIGN_TOP_RIGHT, -3, 0);
  lv_obj_t *bar = lv_bar_create(card);
  lv_obj_set_size(bar, 142, 10);
  lv_obj_set_pos(bar, 4, 32);
  lv_bar_set_range(bar, 0, 100);
  lv_obj_set_style_bg_color(bar, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_bg_color(bar, lv_color_hex(color), LV_PART_INDICATOR);
  lv_obj_t *sub = lv_label_create(card);
  lv_label_set_text(sub, "Waiting for collector");
  lv_obj_set_style_text_color(sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
  lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(sub, 4, 52);
}

EMSCRIPTEN_KEEPALIVE void cyd_init(void) {
  lv_init();
  lv_disp_draw_buf_init(&draw_buffer, buffer, NULL, SCREEN_W * 24);
  static lv_disp_drv_t driver;
  lv_disp_drv_init(&driver);
  driver.hor_res = SCREEN_W;
  driver.ver_res = SCREEN_H;
  driver.flush_cb = flush;
  driver.draw_buf = &draw_buffer;
  lv_disp_drv_register(&driver);

  lv_obj_t *screen = lv_obj_create(NULL);
  // The browser canvas is an exact 320x240 viewport.  The simulator screen
  // must never become a scrollable parent, or LVGL can clip the right column
  // of the Antigravity 2x2 grid even though the physical screen has no scroll.
  lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(screen, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x09090B), LV_PART_MAIN);
  lv_obj_set_style_pad_all(screen, 0, LV_PART_MAIN);
  lv_scr_load(screen);

  mascot = lv_img_create(screen);
  lv_img_set_src(mascot, &mascot_img);
  lv_obj_set_pos(mascot, 6, 3);
  // Reuse the exact Antigravity bitmap used by the physical CYD.  The web
  // preview is therefore a renderer of the device asset, not an HTML "AG"
  // substitute.
  ag_mascot = lv_img_create(screen);
  lv_img_set_src(ag_mascot, &antigravity_mascot_img);
  lv_obj_set_pos(ag_mascot, 6, 3);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  header = lv_label_create(screen);
  lv_label_set_text(header, "Waiting for collector");
  lv_obj_set_style_text_color(header, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
  lv_obj_set_style_text_font(header, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_set_size(header, 230, 20);
  lv_label_set_long_mode(header, LV_LABEL_LONG_DOT);
  lv_obj_set_pos(header, 36, 4);
  plan = lv_label_create(screen);
  lv_label_set_text(plan, LV_SYMBOL_WIFI);
  lv_obj_set_style_text_color(plan, lv_color_hex(0x10B981), LV_PART_MAIN);
  lv_obj_set_pos(plan, 280, 6);

  lv_obj_t *primary = lv_obj_create(screen);
  primary_card = primary;
  lv_obj_set_size(primary, 312, 122);
  lv_obj_set_pos(primary, 4, 30);
  style_card(primary, 0x27272A, 12);
  primary_value = lv_label_create(primary);
  lv_label_set_text(primary_value, "-");
  lv_obj_set_style_text_font(primary_value, &lv_font_montserrat_32, LV_PART_MAIN);
  lv_obj_set_pos(primary_value, 6, 1);
  lv_obj_t *badge = lv_obj_create(primary);
  lv_obj_set_size(badge, 116, 24);
  lv_obj_align(badge, LV_ALIGN_TOP_RIGHT, 0, -2);
  lv_obj_set_style_bg_color(badge, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_border_width(badge, 0, LV_PART_MAIN);
  lv_obj_set_style_radius(badge, 10, LV_PART_MAIN);
  primary_tag = lv_label_create(badge);
  lv_label_set_text(primary_tag, "Usage Limit");
  lv_obj_center(primary_tag);
  primary_bar = lv_bar_create(primary);
  lv_obj_set_size(primary_bar, 296, 14);
  lv_obj_set_pos(primary_bar, 4, 52);
  lv_bar_set_range(primary_bar, 0, 100);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_border_color(primary_bar, lv_color_hex(0x3F3F46), LV_PART_MAIN);
  lv_obj_set_style_border_width(primary_bar, 1, LV_PART_MAIN);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(0x10B981), LV_PART_INDICATOR);
  lv_obj_set_style_radius(primary_bar, 6, LV_PART_MAIN);
  lv_obj_set_style_radius(primary_bar, 6, LV_PART_INDICATOR);
  primary_warn = lv_label_create(primary);
  lv_label_set_text(primary_warn, "100% QUOTA EXHAUSTED");
  lv_obj_set_style_text_color(primary_warn, lv_color_hex(0xF43F5E), LV_PART_MAIN);
  lv_obj_set_style_text_font(primary_warn, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align_to(primary_warn, primary_bar, LV_ALIGN_CENTER, 0, 0);
  lv_obj_add_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
  primary_sub = lv_label_create(primary);
  lv_label_set_text(primary_sub, "Waiting for a CLI result");
  lv_obj_set_style_text_color(primary_sub, lv_color_hex(0x10B981), LV_PART_MAIN);
  lv_obj_set_style_text_font(primary_sub, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(primary_sub, 6, 80);
  lv_obj_t *details = lv_obj_create(screen);
  details_card = details;
  lv_obj_set_size(details, 312, 60);
  lv_obj_set_pos(details, 4, 160);
  style_card(details, 0x27272A, 10);
  credits = lv_label_create(details);
  lv_label_set_recolor(credits, true);
  lv_label_set_text(credits, "Credits: #38bdf8 -#");
  lv_obj_set_style_text_font(credits, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(credits, 6, 12);
  server_status = lv_label_create(details);
  lv_label_set_text(server_status, "ChatGPT");
  lv_obj_set_style_text_color(server_status, lv_color_hex(0x10B981), LV_PART_MAIN);
  lv_obj_set_style_text_font(server_status, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_align(server_status, LV_ALIGN_TOP_RIGHT, -6, 12);

  error_card = lv_obj_create(screen);
  lv_obj_set_size(error_card, 312, 154);
  lv_obj_set_pos(error_card, 4, 48);
  style_card(error_card, 0xF43F5E, 12);
  lv_obj_set_style_bg_color(error_card, lv_color_hex(0x211316), LV_PART_MAIN);
  error_title = lv_label_create(error_card);
  lv_label_set_text(error_title, "Usage unavailable");
  lv_obj_set_style_text_color(error_title, lv_color_hex(0xF43F5E), LV_PART_MAIN);
  lv_obj_set_style_text_font(error_title, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_set_pos(error_title, 7, 10);
  error_detail = lv_label_create(error_card);
  lv_label_set_text(error_detail, "Waiting for the CLI collector.");
  lv_obj_set_style_text_color(error_detail, lv_color_hex(0xF4D7DA), LV_PART_MAIN);
  lv_obj_set_style_text_font(error_detail, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_size(error_detail, 280, 90);
  lv_label_set_long_mode(error_detail, LV_LABEL_LONG_WRAP);
  lv_obj_set_pos(error_detail, 7, 48);
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);

  grid = lv_obj_create(screen);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(grid, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_size(grid, SCREEN_W, SCREEN_H);
  lv_obj_set_pos(grid, 0, 0);
  lv_obj_set_style_bg_opa(grid, LV_OPA_TRANSP, LV_PART_MAIN);
  lv_obj_set_style_border_width(grid, 0, LV_PART_MAIN);
  gemini_heading = lv_label_create(grid);
  lv_label_set_text(gemini_heading, "Gemini Models");
  lv_obj_set_style_text_color(gemini_heading, lv_color_hex(0x2563EB), LV_PART_MAIN);
  lv_obj_set_style_text_font(gemini_heading, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(gemini_heading, 2, 28);
  claude_heading = lv_label_create(grid);
  lv_label_set_text(claude_heading, "Claude Models");
  lv_obj_set_style_text_color(claude_heading, lv_color_hex(0xF97316), LV_PART_MAIN);
  lv_obj_set_style_text_font(claude_heading, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(claude_heading, 162, 28);
  g5 = make_grid_card(grid, "5H Limit", 2, 48, 0x2563EB); finish_grid_card(g5, 0x2563EB);
  c5 = make_grid_card(grid, "5H Limit", 162, 48, 0xF97316); finish_grid_card(c5, 0xF97316);
  gw = make_grid_card(grid, "Weekly", 2, 142, 0x2563EB); finish_grid_card(gw, 0x2563EB);
  cw = make_grid_card(grid, "Weekly", 162, 142, 0xF97316); finish_grid_card(cw, 0xF97316);
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
}

EMSCRIPTEN_KEEPALIVE void cyd_tick(uint32_t elapsed_ms) {
  if (elapsed_ms < 1) elapsed_ms = 1;
  if (elapsed_ms > 100) elapsed_ms = 100;
  lv_tick_inc(elapsed_ms);
  lv_timer_handler();
}

EMSCRIPTEN_KEEPALIVE void cyd_set_codex(const char *account, const char *plan_name, const char *value, const char *tag, const char *sub, const char *credit_value, int used) {
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_label_set_text(plan, LV_SYMBOL_WIFI);
  lv_label_set_text(primary_value, value);
  lv_label_set_text(primary_tag, tag);
  lv_label_set_text(primary_sub, sub);
  lv_label_set_text_fmt(credits, "Credits: #38bdf8 %s#", credit_value);
  lv_label_set_text(server_status, plan_name);
  lv_bar_set_value(primary_bar, 100 - used, LV_ANIM_OFF);
  uint32_t status_color = used > 80 ? 0xF43F5E : used > 50 ? 0xF59E0B : 0x10B981;
  lv_obj_set_style_text_color(primary_value, lv_color_hex(status_color), LV_PART_MAIN);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(status_color), LV_PART_INDICATOR);
  if (used >= 100) lv_obj_clear_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
  else lv_obj_add_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
}

EMSCRIPTEN_KEEPALIVE void cyd_set_antigravity(const char *account, const char *gemini5, const char *gemini5sub, const char *geminiweek, const char *geminiweeksub, const char *claude5, const char *claude5sub, const char *claudeweek, const char *claudeweeksub) {
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_label_set_text(plan, LV_SYMBOL_WIFI);
  lv_obj_add_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_HIDDEN);
  set_grid_card(g5, gemini5, gemini5sub, 0x2563EB);
  set_grid_card(gw, geminiweek, geminiweeksub, 0x2563EB);
  set_grid_card(c5, claude5, claude5sub, 0xF97316);
  set_grid_card(cw, claudeweek, claudeweeksub, 0xF97316);
}

EMSCRIPTEN_KEEPALIVE void cyd_set_error(const char *account, const char *detail) {
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_label_set_text(plan, LV_SYMBOL_WIFI);
  lv_label_set_text(error_detail, detail);
  lv_obj_clear_flag(error_card, LV_OBJ_FLAG_HIDDEN);
}
