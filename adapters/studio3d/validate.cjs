/* First-party wrapper for the pinned Khronos validator; no external resources. */
const fs=require('node:fs'),path=require('node:path');
const validator=require(path.resolve(__dirname,'../../external/gltf-validator/index.js'));
const name=process.argv[2],raw=fs.readFileSync(name);
// Trusted worker output may be a dense high master. Uploads remain capped at
// 96 MiB by the separate host intake validator.
if(raw.length>128*1024**2)throw Error('Validator output input exceeds 128 MiB');
validator.validateBytes(new Uint8Array(raw),{uri:path.basename(name),maxIssues:400,externalResourceFunction:()=>Promise.reject(new Error('External resources disabled'))}).then(report=>process.stdout.write(JSON.stringify(report))).catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
