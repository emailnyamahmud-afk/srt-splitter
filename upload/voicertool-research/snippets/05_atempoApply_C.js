// async function C(audioBuffer, ratio, chunkIndex) — apply ffmpeg.wasm atempo
//
// Decoded algorithm:
//   if (ratio === 1) return audioBuffer;  // no-op if ratio is exactly 1
//   const sampleRate = audioBuffer.sampleRate;
//   const channelData = audioBuffer.getChannelData(0).slice(0);  // copy mono channel
//   const float32Array = new Float32Array(channelData);
//   const uint8View = new Uint8Array(float32Array.buffer);
//   const inputFilename = "in_" + chunkIndex + ".f32";
//   const outputFilename = "out_" + chunkIndex + ".f32";
//   const ffmpegArgs = [
//     "-f", "f32le",     // input format: 32-bit float little-endian PCM
//     "-ar", String(sampleRate),  // input sample rate (24000 from AudioContext)
//     "-ac", "1",         // input channels: mono
//     "-i", inputFilename,
//     "-af", "atempo=" + ratio.toFixed(3),  // AUDIO FILTER: atempo with 3-decimal precision
//     "-f", "f32le",     // output format: same as input
//     outputFilename
//   ];
//   const result = await ffmpeg.exec(ffmpegArgs, inputFilename, uint8View, outputFilename);
//   const resultBytes = result.size / 4;  // f32 = 4 bytes
//   const resultFloat32 = new Float32Array(result.buffer, result.byteOffset, resultBytes / 4);
//   const resultBuffer = audioContext.createBuffer(1, resultFloat32.length, sampleRate);
//   resultBuffer.getChannelData(0).set(resultFloat32);
//   return resultBuffer;
//
// Key points:
//   - Uses ffmpeg.wasm (loaded via getFFmpeg() — caches + import.meta.url patching)
//   - atempo preserves pitch automatically (built-in ffmpeg behavior)
//   - 3-decimal precision: ratio.toFixed(3) (e.g., "atempo=1.234")
//   - Format: f32le mono (32-bit float PCM, single channel)
//   - Sample rate: from AudioContext (likely 24000 Hz — standard Edge TTS)
//   - Virtual FS: each chunk gets unique filename "in_<idx>.f32" / "out_<idx>.f32"

async function C(n,t,u){function i(n,t,r,u,e){return p(t,t-143,r-470,n-687,e-325)}function s(n,t,r,u,e){return f(n-402,t-129,r-451,n,e-150)}function a(n,t,r,u,e){return o(u- -5,t-410,0,t)}function l(n,t,r,u,e){return w(n-83,r,r-23,0,u-1372)}function h(n,t,r,u,e){return p(e,t-102,r-115,r-1604,e-435)}if(!c[s(1631,2068,2644,0,1915)](c[s(1070,1687,992,0,1347)],c[i(1223,952,1845,0,1748)])){if(c[s(346,900,262,0,202)](t,1))return n;const r=n[a(0,904,0,717)+i(1638,1042,1415,0,1631)],e=n[l(1901,0,2089,2156)+s(1083,1741,1663,0,1793)+s(2410,1847,2368,0,1876)](0),o=new Float32Array(e),f=new Uint8Array(o[l(2789,0,1928,2163)+"r"]),d=s(1558,1347,2057,0,1957)+"n_"+u+s(438,799,178,0,124),W=h(0,1769,1299,0,909)+l(1826,0,1443,1703)+u+s(236,799,54,0,1344),w=["-f",c[i(352,845,893,0,905)],c[i(630,299,1404,0,1287)],r[i(929,635,627,0,755)+l(1619,0,1539,2126)](),c[h(0,1725,1764,0,2137)],"1","-i",d,c[h(0,1517,1938,0,1490)],s(1251,601,66,0,937)+"o="+t[s(1649,1624,1105,0,1499)+"ed"](3),"-f",c[s(1036,816,1457,0,580)],W],p=await m[s(720,675,370,0,564)+s(2008,1575,982,0,1115)+"d"](w,d,f,W),g=c[s(1103,1417,1893,0,1482)](Math[a(0,98,0,-393)](c[l(1462,0,1669,940)](p[a(0,-185,0,127)+s(258,767,1346,0,1514)],4)),4),y=new Float32Array(p[s(1292,1866,1682,0,1734)+"r"],p[i(372,868,707,0,-109)+h(0,2228,1884,0,2209)],c[i(179,728,-407,0,-121)](g,4)),C=audiovo[h(0,1094,1437,0,1865)+a(0,883,0,162)+"er"](1,y[h(0,1286,1669,0,1901)+"h"],r);return C[i(1395,1879,1155,0,655)+s(1685,1741,999,0,2351)+a(0,39,0,776)](0)[h(0,1855,2469,0,2170)](y),C}e=r[h(0,2725,2109,0,2261)+"ce"](/[.!?*@#—,।॥។।،؟，。…‼؛：]/gu,"")}