import {build} from 'esbuild';
await build({entryPoints:['renderer/export.tsx'],bundle:true,platform:'node',format:'esm',packages:'external',outfile:'renderer/dist/export.mjs',jsx:'automatic'});
console.log('Local React/SVG renderer ready.');
