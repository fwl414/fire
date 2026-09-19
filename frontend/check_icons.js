const icons = require('@element-plus/icons-vue');
const names = new Set(Object.keys(icons));
const fs = require('fs');
const path = require('path');
function walk(dir){ let r=[]; for(const e of fs.readdirSync(dir,{withFileTypes:true})){ const p=path.join(dir,e.name); if(e.isDirectory()) r=r.concat(walk(p)); else if(e.name.endsWith('.vue')) r.push(p);} return r;}
const files = walk('src');
const bad = new Map();
for(const f of files){
  const c = fs.readFileSync(f,'utf8');
  const m = c.match(/import\s*\{([^}]*)\}\s*from\s*['"]@element-plus\/icons-vue['"]/s);
  if(!m) continue;
  const imps = m[1].split(',').map(s=>s.trim()).filter(Boolean);
  for(const i of imps){ if(!names.has(i)){ if(!bad.has(i)) bad.set(i,[]); bad.get(i).push(path.relative('src',f)); } }
}
for(const [icon, flist] of bad){ console.log(icon + ' -> ' + flist.length + ' file(s): ' + flist.join(', ')); }
console.log('TOTAL BAD ICONS:', bad.size);
