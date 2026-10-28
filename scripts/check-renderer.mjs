import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
await build({entryPoints:['renderer/verify.tsx'],bundle:true,platform:'node',format:'esm',packages:'external',outfile:'renderer/dist/verify.mjs',jsx:'automatic'});
const result=spawnSync(process.execPath,['renderer/dist/verify.mjs'],{stdio:'inherit',windowsHide:true});
process.exitCode=result.status??1;
