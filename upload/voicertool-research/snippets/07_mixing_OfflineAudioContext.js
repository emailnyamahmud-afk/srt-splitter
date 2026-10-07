// Mixing: render all per-cue buffers into a single AudioBuffer via OfflineAudioContext
//
// Decoded algorithm:
//   // Run all per-cue async ops in batches of 1 (sequential, not parallel)
//   const results = [];
//   for (let i = 0; i < O.length; i += 1) {
//     const batch = O.slice(i, i + 1);
//     results.push(...await Promise.all(batch.map(fn => fn())));
//   }
//
//   const sampleRate = audioContext.sampleRate;  // 24000 Hz
//   // Total duration: max(cue.end + cue.audioBuffer.duration) across all cues
//   const totalDur = Math.max(...results.map(r => r.offsetSeconds + r.audioBuffer.duration));
//   const totalSamples = Math.max(totalDur * 0.2, sampleRate);  // at least 1 sample
//   const offlineCtx = new OfflineAudioContext(1, totalSamples, sampleRate);
//
//   for (const { audioBuffer, offsetSeconds } of results) {
//     const source = offlineCtx.createBufferSource();
//     source.buffer = audioBuffer;
//     source.connect(offlineCtx.destination);
//     source.start(offsetSeconds);  // place at cue.start in seconds
//   }
//
//   const rendered = await offlineCtx.startRendering();
//   // Then encode as WAV (RIFF/WAVE/fmt/data header) — see _0x9856 array
//
// KEY INSIGHTS:
//   - Each cue is placed at offset = cue.start (SRT start time)
//   - If two cues overlap (audio from cue N extends into cue N+1 start),
//     OfflineAudioContext SUMS them (mix-down) — no crossfade, just additive overlap
//   - Total length = max of (cue.end + audioDur) — preserves any trailing audio
//   - NO crossfade between cues (additive mix only on overlap)
//   - NO audio normalization (TTS amplitude preserved as-is)

x=[];for(let n=0;c[f(413,695,1371,1227,1085)](n,O[Y(724,786,1013,1553,647)+"h"]);n+=1){const t=O[Y(806,962,572,925,1181)](n,c[f(144,827,1065,1546,388)](n,1));x[Y(1249,1001,1550,1065,1681)](...await Promise[w(204,-767,-172,0,-391)](t[Y(2030,1571,1820,2e3,1548)](n=>n())))}function Y(n,t,r,u,e){return Wg(r-239,t-393,r-341,n,e-68)}const b=audiovo[Y(1549,1429,1585,0,1081)+p(1669,434,1133,951,1550)],k=Math[w(467,1646,322,0,1053)](...x[w(1340,1607,1638,0,948)](n=>n[o(78,219,0,-395)+o(51,56,0,651)+Y(1411,1171,892,0,1534)]+n[f(643,1215,562,786,1399)+f(1816,1631,2189,2139,2343)+"r"][Y(1851,1436,1793,0,2492)+Y(332,107,626,0,940)])),E=Math[w(1255,455,1240,0,545)](c[o(351,361,0,-56)](c[p(733,819,187,907,1096)](k,.2),b)),S=new OfflineAudioContext(1,E,b);for(const{audioBuffer:n,offsetSeconds:t}of x){const r=S[f(491,855,1307,832,578)+p(208,783,263,82,34)+o(569,891,0,-161)+p(64,1317,1286,611,1190)]();r[Y(1744,1963,1663,0,2268)+"r"]=n,r[f(1543,1918,1432,1844,1388)+"ct"](S[p(952,1551,1583,852,95)+f(1496,1942,2110,2572,2401)+"n"]),r[f(1324,1008,1028,1174,1122)](t)}const M=await S[w(-387,-551,658,0,62)+w(1037,197,1320,0,902)+o(76,31,0,-262)]();if(c[Y(1184,1430,1474,0,2182)](h,c[w(1014,597,276,0,263)])){return await c[p(934,1478,852,891,950)](ab,M)}if(c[o(1015,1346,0,884)](h,c[f(499,1091,1459,864,1452)])){return await c[w(292,-752,-607,0,-345)](uf,M)}}