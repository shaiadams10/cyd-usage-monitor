#ifndef CYD_UI_PROVIDER_H
#define CYD_UI_PROVIDER_H
/* Shared vector marks and 320x240 layout vocabulary for hardware and WASM.
 * Provider-inspired symbols, not certified artwork. No raster buffers or
 * per-frame allocations; the same fixed line geometry is published to HTML. */
#include <lvgl.h>
#include <math.h>
#include <string.h>
#include <stdint.h>
static lv_point_t cyd_provider_lines[2][96];
static unsigned cyd_provider_count[2];
static void cyd_provider_geometry(void) {
    if (cyd_provider_count[0]) return;
    const float pi = 3.14159265359f;
    /* Six interlocking monoline lobes, with a clear open center. */
    const float loop[][2] = {{-1,-4},{-5,-6},{-6,-10},{-3,-13},{2,-13},{6,-10},{6,-5},{1,-2}};
    unsigned n = 0;
    for (unsigned k=0;k<6;++k) {
        float a=k*pi/3, c=cosf(a), s=sinf(a);
        for (unsigned j=0;j<7;++j) {
            for (unsigned p=j;p<=j+1;++p) {
                cyd_provider_lines[0][n].x=(lv_coord_t)lroundf(16+loop[p][0]*c-loop[p][1]*s);
                cyd_provider_lines[0][n++].y=(lv_coord_t)lroundf(16+loop[p][0]*s+loop[p][1]*c);
            }
        }
    }
    cyd_provider_count[0]=n;
    n=0;
    for (unsigned k=0;k<12;++k) {
        float a=k*pi/6+.07f, outer=k%3==0?15: k%2?12:14;
        cyd_provider_lines[1][n].x=(lv_coord_t)lroundf(16+3*cosf(a));
        cyd_provider_lines[1][n++].y=(lv_coord_t)lroundf(16+3*sinf(a));
        cyd_provider_lines[1][n].x=(lv_coord_t)lroundf(16+outer*cosf(a));
        cyd_provider_lines[1][n++].y=(lv_coord_t)lroundf(16+outer*sinf(a));
    }
    cyd_provider_count[1]=n;
}
static void cyd_provider_icon_draw(lv_event_t *event) {
    lv_obj_t *obj=lv_event_get_target(event);
    unsigned provider=(unsigned)(uintptr_t)lv_event_get_user_data(event);
    lv_draw_ctx_t *ctx=lv_event_get_draw_ctx(event);
    lv_area_t area;lv_obj_get_coords(obj,&area);
    int width=lv_obj_get_width(obj),height=lv_obj_get_height(obj);
    lv_draw_line_dsc_t line;lv_draw_line_dsc_init(&line);
    line.color=lv_color_hex(provider?0xD97757:0xB6F2DD);
    line.width=width>=30?2:1;line.round_start=1;line.round_end=1;
    for (unsigned i=0;i<cyd_provider_count[provider];i+=2) {
        lv_point_t p1={(lv_coord_t)(area.x1+cyd_provider_lines[provider][i].x*width/32),(lv_coord_t)(area.y1+cyd_provider_lines[provider][i].y*height/32)};
        lv_point_t p2={(lv_coord_t)(area.x1+cyd_provider_lines[provider][i+1].x*width/32),(lv_coord_t)(area.y1+cyd_provider_lines[provider][i+1].y*height/32)};
        lv_draw_line(ctx,&line,&p1,&p2);
    }
}
static lv_obj_t *cyd_provider_icon(lv_obj_t *screen,bool claude,int width) {
    cyd_provider_geometry();
    lv_obj_t *obj=lv_obj_create(screen);lv_obj_remove_style_all(obj);
    lv_obj_set_size(obj,width,width);lv_obj_clear_flag(obj,LV_OBJ_FLAG_SCROLLABLE|LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(obj,cyd_provider_icon_draw,LV_EVENT_DRAW_MAIN,(void*)(uintptr_t)(claude?1:0));
    lv_obj_add_flag(obj,LV_OBJ_FLAG_HIDDEN);return obj;
}
typedef struct {
    lv_obj_t *screen,*primary,*weekly,*primary_value,*weekly_value,*primary_tag,*weekly_tag;
    lv_obj_t *primary_sub,*weekly_sub,*primary_bar,*weekly_bar,*warning,*eyebrow;
} cyd_provider_view;
static void cyd_place(lv_obj_t *obj,int x,int y,int w,int h,int sx,int sy) {
    lv_obj_set_pos(obj,x*sx/320,y*sy/240);
    if(w>=0)lv_obj_set_width(obj,w*sx/320);
    if(h>=0)lv_obj_set_height(obj,h*sy/240);
}
static void cyd_compact_reset(lv_obj_t *label) {
    const char *source=lv_label_get_text(label);char text[180];
    snprintf(text,sizeof(text),"%s",source);
    char *zone=strstr(text," (");
    if(zone&&(strchr(zone,'/')||strstr(zone,"UTC")||strstr(zone,"GMT"))) *zone=0;
    lv_label_set_text(label,text);
}
static void cyd_compact_plan(lv_obj_t *label,const char *source) {
    /* Compact before setting the label: LV_LABEL_LONG_DOT may mutate its
     * stored text, so a prior truncated label is not an authoritative source. */
    lv_label_set_text(label,strncmp(source,"ChatGPT ",8)==0?source+8:source);
    lv_label_set_long_mode(label,LV_LABEL_LONG_DOT);
}
static void cyd_provider_theme(cyd_provider_view *v,bool claude,int sx,int sy) {
    uint32_t bg=claude?0x17120F:0x0D1715, card=claude?0x241B16:0x14241F;
    uint32_t border=claude?0x52382B:0x2B4C40,muted=claude?0xBDAA9B:0x9AB7AB;
    uint32_t accent=claude?0xD97757:0x43D9AA;
    lv_obj_set_style_bg_color(v->screen,lv_color_hex(bg),0);
    lv_obj_t *cards[]={v->primary,v->weekly};
    for(unsigned i=0;i<2;++i){
        lv_obj_set_style_pad_all(cards[i],0,0);
        lv_obj_set_style_bg_color(cards[i],lv_color_hex(card),0);
        lv_obj_set_style_border_color(cards[i],lv_color_hex(border),0);
        lv_obj_set_style_border_width(cards[i],1,0);
        lv_obj_set_style_radius(cards[i],14,0);
        lv_obj_clear_flag(cards[i],LV_OBJ_FLAG_SCROLLABLE);
    }
    /* Keep the warning out of either quota card so it spans the whole layout. */
    lv_obj_set_parent(v->warning,v->screen);
    lv_obj_set_style_text_font(v->warning,&lv_font_montserrat_12,0);
    lv_obj_set_style_bg_opa(v->warning,LV_OPA_TRANSP,0);
    lv_obj_set_style_pad_all(v->warning,0,0);
    lv_obj_set_style_text_color(v->warning,lv_color_hex(0xFDA49A),0);
    cyd_place(v->warning,10,220,300,18,sx,sy);
    lv_obj_set_style_text_align(v->warning,LV_TEXT_ALIGN_CENTER,0);
    lv_obj_set_style_text_font(v->eyebrow,&lv_font_montserrat_12,0);
    lv_obj_set_style_text_color(v->eyebrow,lv_color_hex(accent),0);
    lv_label_set_text(v->eyebrow,claude?"CLAUDE CODE  /  PLAN USAGE":"OPENAI CODEX  /  PLAN USAGE");
    cyd_place(v->eyebrow,10,33,300,16,sx,sy);
    lv_obj_clear_flag(v->eyebrow,LV_OBJ_FLAG_HIDDEN);
    lv_obj_t *subs[]={v->primary_sub,v->weekly_sub};
    lv_obj_t *tags[]={v->primary_tag,v->weekly_tag};
    lv_obj_t *bars[]={v->primary_bar,v->weekly_bar};
    for(unsigned i=0;i<2;++i){
        lv_obj_set_style_text_color(subs[i],lv_color_hex(muted),0);
        lv_obj_set_style_text_font(subs[i],&lv_font_montserrat_12,0);
        lv_label_set_long_mode(subs[i],LV_LABEL_LONG_WRAP);
        cyd_compact_reset(subs[i]);
        lv_obj_set_style_text_font(tags[i],&lv_font_montserrat_12,0);
        lv_obj_set_style_text_color(tags[i],lv_color_hex(muted),0);
        lv_obj_set_style_bg_color(bars[i],lv_color_hex(claude?0x513B30:0x304D41),LV_PART_MAIN);
        lv_obj_set_style_bg_opa(bars[i],LV_OPA_COVER,LV_PART_MAIN);
        lv_obj_set_style_border_width(bars[i],0,0);
        lv_obj_set_style_radius(bars[i],7,0);lv_obj_set_style_radius(bars[i],7,LV_PART_INDICATOR);
    }
    /* Badge belongs to the original Codex card; remove its decorative shell. */
    lv_obj_t *badge=lv_obj_get_parent(v->primary_tag);
    if(badge!=v->primary){lv_obj_remove_style_all(badge);cyd_place(badge,12,10,120,18,sx,sy);}
    lv_obj_set_pos(v->primary_tag,0,0);
    lv_label_set_text(v->primary_tag,"5-hour remaining");
    lv_label_set_text(v->weekly_tag,"Weekly remaining");
    /* Equal, distance-readable windows for both providers. The thick tracks
     * carry the quota at a glance; resets and the footer stay secondary. */
    cyd_place(v->primary,8,56,148,145,sx,sy);cyd_place(v->weekly,164,56,148,145,sx,sy);
    cyd_place(v->primary_value,12,34,124,40,sx,sy);cyd_place(v->weekly_value,12,34,124,40,sx,sy);
    cyd_place(v->weekly_tag,12,10,125,18,sx,sy);
    cyd_place(v->primary_bar,12,82,124,20,sx,sy);cyd_place(v->weekly_bar,12,82,124,20,sx,sy);
    cyd_place(v->primary_sub,12,111,124,30,sx,sy);cyd_place(v->weekly_sub,12,111,124,30,sx,sy);
    lv_obj_set_style_text_font(v->primary_value,&lv_font_montserrat_32,0);
    lv_obj_set_style_text_font(v->weekly_value,&lv_font_montserrat_32,0);
    lv_obj_t *values[]={v->primary_value,v->weekly_value};
    for(unsigned i=0;i<2;++i){
        char text[64];snprintf(text,sizeof(text),"%s",lv_label_get_text(values[i]));
        char *left=strstr(text," left");if(left)*left=0;
        lv_label_set_text(values[i],text);
        bool available=strchr(text,'%')!=NULL;
        int remaining=atoi(text);
        uint32_t color=!available?0x8A929C:remaining<=20?0xF47C6B:remaining<=50?0xE9B56F:accent;
        lv_obj_set_style_bg_color(bars[i],lv_color_hex(color),LV_PART_INDICATOR);
        lv_obj_set_style_text_color(values[i],lv_color_hex(available&&remaining>20?(claude?0xF4E8D8:0xEFFAF5):color),0);
    }
}
#endif
