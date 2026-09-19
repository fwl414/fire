const icons = require('@element-plus/icons-vue');
const names = Object.keys(icons).sort();
// Fire-related, weather, device, UI icons
const keywords = ['fire','flame','hot','warm','cold','water','drop','wind','gas','smoke','light','bulb','bell','alert','warn','info','help','setting','tool','shield','first','aid','medic','cross','plus','check','close','edit','delete','search','view','hide','message','chat','notification','history','time','clock','calendar','location','map','user','people','phone','video','camera','image','picture','picture','document','file','folder','upload','download','refresh','loading','link','connection','link','cpu','monitor','screen','mobile','phone','battery','power','switch','sunny','moon','star','heart','share','star','aim','target','odometer','reading','scale','microscope','experiment','box','package','truck','car','van','house','office','school','building','shop','store','medicine','pill','first-aid','ambulance','siren','alarm-bell','warning','info-filled','warning-filled','circle-check','circle-close','reading'];
const found = names.filter(n => keywords.some(k => n.toLowerCase().includes(k)));
console.log(found.join('\n'));
