const fs = require('fs');
const path = require('path');

const mapping = {
  Fire: 'Warning',
  Thermometer: 'ColdDrink',
  Drop: 'ColdDrink',
  Hand: 'Tools',
  Flame: 'Warning',
  Wind: 'WindPower',
  Water: 'ColdDrink',
  FirstAid: 'FirstAidKit',
  Shield: 'Warning',
  FireExtinguisher: 'Box',
  Cigarette: 'Warning',
  History: 'Clock',
  Bulb: 'Sunny',
  Alert: 'Bell',
  Info: 'InfoFilled',
  Read: 'Reading',
  WarnTriangle: 'WarnTriangleFilled',
  Signal: 'Connection',
  Battery: 'Odometer',
  MessageFilled: 'MessageBox',
  Bold: 'Edit',
  Italic: 'EditPen',
  Underline: 'Document',
};

function walk(dir){ let r=[]; for(const e of fs.readdirSync(dir,{withFileTypes:true})){ const p=path.join(dir,e.name); if(e.isDirectory()) r=r.concat(walk(p)); else if(e.name.endsWith('.vue')) r.push(p);} return r;}

const files = walk('src');
let changed = 0;
for(const f of files){
  let c = fs.readFileSync(f,'utf8');
  let modified = false;
  // replace template usage <OldIcon /> and <OldIcon>
  for(const [oldI, newI] of Object.entries(mapping)){
    const re = new RegExp('\\b' + oldI + '\\b', 'g');
    if(re.test(c)){
      c = c.replace(re, newI);
      modified = true;
    }
  }
  // deduplicate import list from @element-plus/icons-vue
  c = c.replace(/import\s*\{([^}]*)\}\s*from\s*['"]@element-plus\/icons-vue['"]/s, (match, imps) => {
    const list = imps.split(',').map(s=>s.trim()).filter(Boolean);
    const uniq = [...new Set(list)];
    return 'import { ' + uniq.join(', ') + " } from '@element-plus/icons-vue'";
  });
  if(modified){
    fs.writeFileSync(f, c, 'utf8');
    changed++;
    console.log('updated:', path.relative('src', f));
  }
}
console.log('TOTAL FILES CHANGED:', changed);
