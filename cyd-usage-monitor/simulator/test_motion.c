/* Run with simulator/build-wasm.ps1 -TestMotion. Uses the real LVGL runtime. */
#include <assert.h>
#include "lvgl_cyd_sim.c"

static void advance(unsigned ms) {
    for (unsigned i = 0; i < ms; i += 33) cyd_tick(33);
}
static void codex(int used) {
    cyd_set_codex("Demo Codex", "25% used", "5H Limit", "Resets later", used,
                  "65% left", "Weekly reset", 35);
}
int main(void) {
    EM_ASM({
        globalThis.window = {};
        Module.canvas = {getContext: () => ({
            createImageData: (w,h) => ({data: new Uint8ClampedArray(w*h*4)}),
            putImageData: () => {}
        })};
    });
    cyd_init(); advance(500);
    cyd_show_usage(); advance(500); codex(25); advance(1100);
    assert(lv_bar_get_value(primary_bar) == 750);
    assert(lv_bar_get_value(weekly_bar) == 650);
    /* Returning to a populated screen used to reset values after arrival. */
    cyd_show_launcher(); advance(700);
    cyd_show_usage(); advance(99);
    int revealed = cyd_navigation_revealed;
    assert(revealed > 0 && revealed < SCREEN_W);
    assert(lv_obj_get_x(usage_screen) == 0);
    assert(lv_obj_get_x(launcher_screen) == 0); /* departing screen stays still */
    cyd_show_usage(); /* duplicate command cannot restart the slide */
    assert(cyd_navigation_revealed == revealed);
    advance(500);
    assert(lv_bar_get_value(primary_bar) == 750 && !cyd_bars[0].running);
    assert(lv_obj_get_style_translate_y(primary_card, 0) == 0);
    cyd_set_codex("Second account", "25% used", "5H", "Reset", 25,
                  "65% left", "Weekly", 35);
    advance(66);
    assert(lv_bar_get_value(primary_bar) == 750); /* no zero flash on identity */
    codex(25); advance(1100);
    codex(60); advance(200);
    int middle = lv_bar_get_value(primary_bar);
    assert(middle > 400 && middle < 750);
    uint32_t started = cyd_bars[0].started;
    codex(60); assert(cyd_bars[0].started == started); /* cached reads do not restart */
    codex(80); advance(1100); assert(lv_bar_get_value(primary_bar) == 200);
    codex(0); advance(1100); assert(lv_bar_get_value(primary_bar) == 1000);
    codex(100); advance(1100); assert(lv_bar_get_value(primary_bar) == 0);
    codex(120); advance(1100); assert(lv_bar_get_value(primary_bar) == 0);
    codex(-20); advance(1100); assert(lv_bar_get_value(primary_bar) == 1000);
    advance(30000); codex(-20); assert(cyd_bars[0].shine);
    advance(1100); assert(!cyd_bars[0].shine);

    cyd_set_antigravity("Demo AG", "90%", "Reset later", "65%", "Reset later", "40%", "Reset later", "20%", "Reset later");
    advance(1100);
    assert(lv_bar_get_value(lv_obj_get_child(g5, 2)) == 900);
    assert(lv_bar_get_value(lv_obj_get_child(c5, 2)) == 400);
    assert(lv_bar_get_value(lv_obj_get_child(gw, 2)) == 650);
    assert(lv_bar_get_value(lv_obj_get_child(cw, 2)) == 200);
    cyd_set_error("Demo AG", "Unavailable"); advance(1100);
    assert(!lv_obj_has_flag(error_card, LV_OBJ_FLAG_HIDDEN));

    cyd_show_openrouter(); advance(500);
    cyd_set_openrouter("Demo Router", "$24.75", 75, "$1.20", "$6.80", "$15.25", "Demo model", 10,20,35,40,60,80,100);
    advance(200); assert(lv_arc_get_value(or_arc) > 0 && lv_arc_get_value(or_arc) < 750);
    advance(1100); assert(lv_arc_get_value(or_arc) == 750);
    assert(strcmp(lv_label_get_text(or_balance), "$24.75") == 0);
    assert(strcmp(lv_label_get_text(or_month), "$15.25") == 0);
    assert(cyd_chart_now[6] == 100);
    cyd_set_openrouter("Demo Router", "$10.00", 30, "$2.20", "$7.80", "$16.25", "Demo model", 30,20,35,40,60,80,90);
    advance(100);
    cyd_set_openrouter("Demo Router", "--", 0, "--", "--", "--", "Unavailable", 0,0,0,0,0,0,0);
    advance(1200);
    assert(strcmp(lv_label_get_text(or_balance), "--") == 0);
    assert(lv_arc_get_value(or_arc) == 0 && !cyd_chart_running);
    for (unsigned i = 0; i < 7; ++i) assert(cyd_chart_now[i] == 0);

    /* Rapid screen changes during active motion must not leave offsets or
     * orphan animations; hidden bars finish rather than retaining old data. */
    for (unsigned i = 0; i < 40; ++i) {
        cyd_show_usage(); codex(i % 100); advance(66);
        cyd_show_openrouter(); advance(66);
        cyd_show_launcher(); advance(66);
    }
    advance(1500);
    assert(lv_scr_act() == launcher_screen);
    assert(!cyd_bars[0].running);
    assert(lv_obj_get_style_translate_y(primary_card, 0) == 0);
    puts("PASS: quota drains/refills, stable arrival/account values, stationary departing screen, duplicate routes, retargeting, cached reads, refresh sweep, bounds, credit/chart motion, error cancellation, rapid navigation");
    return 0;
}
