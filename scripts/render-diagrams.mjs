import {readFile,readdir,writeFile} from 'node:fs/promises';
import {instance} from '@viz-js/viz';
const viz=await instance();
const graphs={};
for(const name of (await readdir('docs/diagrams')).filter(name=>name.endsWith('.dot')).sort()){
  const source=await readFile(`docs/diagrams/${name}`,'utf8');
  const svg=viz.renderString(source,{format:'svg',engine:'dot'});
  graphs[name]=svg;
  if(process.argv.includes('--write'))await writeFile(`docs/diagrams/${name.replace(/\.dot$/,'.svg')}`,svg);
}
if(!process.argv.includes('--write'))process.stdout.write(JSON.stringify({graphviz:viz.graphvizVersion,graphs}));
