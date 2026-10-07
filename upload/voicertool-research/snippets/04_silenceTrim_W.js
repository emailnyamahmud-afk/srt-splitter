// function W(audioBuffer, headThreshold=0.01, tailThreshold=0.0036) — silence trim
//
// Decoded algorithm:
//   const data = audioBuffer.getChannelData(0);
//   let f = 0, a = data.length - 1;
//   // Trim head: skip samples where |sample| < 0.01 (-40 dBFS)
//   while (f < a && Math.abs(data[f]) < headThreshold) f++;
//   // Trim tail: skip samples where |sample| < 0.0036 (-48.9 dBFS)
//   while (a > f && Math.abs(data[a]) < tailThreshold) a--;
//   const length = a - f + 1;
//   const newBuffer = audioContext.createBuffer(1, length, audioBuffer.sampleRate);
//   newBuffer.getChannelData(0).set(data.slice(f, a + 1), 0);
//   return newBuffer;
//
// Thresholds:
//   - 0.01 linear = -40 dBFS (head silence trim — aggressive)
//   - 0.0036 linear = -48.87 dBFS (tail silence trim — gentler, preserves trailing consonants)
//   - Asymmetric: head uses higher threshold, tail uses lower threshold

function W(n,r=.01,u=.0036){function e(n,t,r,u,e){return p(e,t-50,r-316,t-609,e-319)}function o(n,t,r,u,e){return p(t,t-223,r-160,e- -72,e-273)}function i(n,t,r,u,e){return f(n-281,u- -1161,r-414,e,e-111)}function s(n,t,r,u,e){return f(n-418,r- -1253,r-296,n,e-221)}if(c[s(-713,0,-127,0,-248)](c[s(-1364,0,-613,0,133)],c[e(0,227,819,0,-111)])){const n={};return t[e(0,1114,379,0,641)+"ce"](/([a-zA-Z][a-zA-Z0-9\-]*)="([^"]*)"/g,(t,r,u)=>{n[r]=u}),n}{const t=n[s(-203,0,477,0,1119)+i(1139,0,29,451,461)+i(655,0,985,557,76)](0);let f=0,a=c[e(0,76,453,0,-589)](t[i(-803,0,-602,-74,-438)+"h"],1);for(;c[s(-496,0,-241,0,-646)](f,a)&&c[i(-275,0,-248,-149,483)](Math[s(125,0,-616,0,-808)](t[f]),r);)f++;for(;c[e(0,1222,1477,0,1131)](a,f)&&c[s(-1053,0,-558,0,-1169)](Math[s(-816,0,-616,0,-363)](t[a]),u);)a--;const l=c[i(545,0,138,478,900)](c[e(0,76,-231,0,-657)](a,f),1),h=audiovo[i(-43,0,-857,-306,20)+o(0,-61,-323,0,10)+"er"](1,l,n[o(0,959,514,0,565)+o(0,512,773,0,879)]);return h[i(712,0,724,98,-654)+i(563,0,176,-122,611)+e(0,560,525,0,646)](t[i(705,0,164,755,101)+i(141,0,-18,-76,-423)](f,c[o(0,1061,875,0,782)](a,1)),0,0),h}}