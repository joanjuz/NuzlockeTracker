'use strict';
const assert=require('node:assert/strict');
const layout=require('../web/overlay-layout.js');
const config={slot_width:142,sprite_size:94,gap:16,name_size:20,hp_height:17,hp_text_size:13,
  hp_label:'fraction',item_size:14,item_icon_size:32,item_display:'both',info_size:14,
  graveyard_max:12,graveyard_columns:6,graveyard_sprite_size:64,graveyard_title:true,
  graveyard_show_name:true,graveyard_show_level:true,graveyard_show_route:true};
for(const count of [1,6,12,30])for(const mode of ['horizontal','vertical','grid','custom']){
  const box=layout.measure({...config,graveyard_layout:mode,graveyard_max:count},6);
  assert.equal(box.graveColumns,mode==='horizontal'?count:mode==='vertical'?1:mode==='grid'?Math.min(6,count):6);
  assert.equal(box.graveRows,Math.ceil(count/box.graveColumns));
  assert.ok(box.graveyard.width>0&&box.graveyard.height>0);
}
assert.equal(layout.measure(config,1).sprites.width,142);
assert.equal(layout.measure(config,6).sprites.width,932);
assert.equal(layout.measure({...config,frame_enabled:true,frame_width:8},6).all.height,layout.measure(config,6).all.height);
assert.equal(layout.measure({...config,frame_names_height:75},6).names.height,75);
assert.deepEqual(layout.measure({...config,nickname:'x'.repeat(999)},6),layout.measure(config,6));
assert.equal(layout.measure({...config,graveyard_layout:'vertical'},6).graveyard.width,142);
console.log('PASS deterministic overlay bounds and all graveyard layouts');
