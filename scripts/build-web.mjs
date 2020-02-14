import {copyFile, mkdir} from 'node:fs/promises';
await mkdir('dist/assets', {recursive:true});
await copyFile('web/index.html','dist/index.html');
await copyFile('web/style.css','dist/assets/style.css');
