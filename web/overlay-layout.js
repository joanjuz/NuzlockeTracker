'use strict';
/* Shared source geometry: depends on profile settings, never on live content. */
const OverlayLayout = (() => {
  function measure(c,n=6){
    const gap=c.gap??16,slot=c.slot_width||142;
    const columns=c.direction==='column'?1:c.direction==='grid'?Math.min(3,n):n;
    const rows=Math.ceil(n/columns),width=columns*slot+(columns-1)*gap;
    const line=size=>Math.ceil(size*1.3);
    const heights={sprites:c.sprite_size||94,names:c.frame_names_height||line(c.name_size||20)+4,
      hp:(c.hp_height||17)+(c.hp_label==='none'?0:4+line(c.hp_text_size||13)),
      items:c.frame_items_height||((c.item_display==='name'?0:(c.item_icon_size||32)+2)+
        (c.item_display==='icon'?0:line(c.item_size||14)*2)+4),
      info:c.frame_info_height||Math.ceil((c.info_size||14)*1.45)*3+4};
    const result={slotHeights:heights};
    for(const [key,h] of Object.entries(heights))result[key]={width,height:rows*h+(rows-1)*gap};
    const max=c.graveyard_max||12,mode=c.graveyard_layout||'custom';
    const cols=mode==='horizontal'?max:mode==='vertical'?1:mode==='grid'?Math.min(6,max):(c.graveyard_columns||6);
    const graveRows=Math.ceil(max/cols),graveGap=c.graveyard_gap??gap;
    const text=[c.graveyard_show_name,c.graveyard_show_species,c.graveyard_show_level,c.graveyard_show_route]
      .filter(Boolean).length*line((c.name_size||20)*.8);
    const cardHeight=(c.graveyard_sprite_size||64)+text+4;
    result.graveColumns=cols;result.graveRows=graveRows;result.graveCardHeight=cardHeight;
    result.graveyard={width:cols*Math.max(slot,c.graveyard_sprite_size||64)+(cols-1)*graveGap,
      height:(c.graveyard_title?line(c.name_size||20)+6:0)+graveRows*cardHeight+(graveRows-1)*graveGap};
    const icon=c.counter_icon_size||36,total=c.counter_total||10;
    result.counter={width:c.counter_mode==='lives'?Math.max(slot,total*(icon+8)+120):slot,
      height:Math.max(icon,line(c.name_size||20))+8};
    const shown=['captures','deaths','alive','missed'].filter(key=>c['stats_show_'+key]!==false).length;
    const statWidth=Math.ceil((c.stats_size||20)*12);
    result.stats={width:c.stats_direction==='column'?statWidth:Math.max(1,shown)*statWidth+Math.max(0,shown-1)*(c.stats_size||20)*.7,
      height:c.stats_direction==='column'?Math.max(1,shown)*line(c.stats_size||20):line(c.stats_size||20)+4};
    const layers=['sprites','names','hp'];
    if(c.items_in_composition)layers.push('items');
    if(c.info_in_composition)layers.push('info');
    if(c.counter_in_composition&&c.counter_mode!=='off')layers.push('counter');
    result.all={width:Math.max(...layers.map(key=>result[key].width)),
      height:layers.reduce((sum,key)=>sum+result[key].height,0)+(layers.length-1)*gap};
    return result;
  }
  return Object.freeze({measure});
})();
if(typeof module!=='undefined')module.exports=OverlayLayout;
