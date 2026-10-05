// function y(audioDur, cueDur) — Voicertool speed_setting ratio computation
//
// Decoded algorithm (based on raw text analysis):
//   let o = audioDur / cueDur  (raw ratio)
//   if (speed_setting === "1") {       // SPEED UP ONLY mode
//     if (o < 1) o = 1;                // floor: never slow down
//     o = Math.min(2, o);              // cap: max 2x speed up
//   } else if (speed_setting === "2") { // SPEED UP AND SLOW DOWN mode
//     o = Math.min(2, Math.max(0.68, o)); // floor 0.68 (max slowdown ~1.47x), cap 2 (max speedup 2x)
//   } else {
//     o = 1;                          // default: no change
//   }
//   return o;
//
// Key constants:
//   - 1.0 = floor for speedup-only mode (never slow down)
//   - 0.68 = floor for speedup-slowdown mode (max slowdown 1/0.68 ≈ 1.47x)
//   - 2.0 = ceil for both modes (max speedup 2x)
//
// Note: speed_setting is read from DOM (dropdown value as string "1" or "2")
//       Confirmed in 2 places: offset 63393 (earlier in code) and here in y()

function y(n,t){function u(n,t,r,u,e){return p(t,t-409,r-316,r-551,e-2)}function s(n,t,r,u,e){return w(n-349,r,r-82,0,e-855)}function l(n,t,r,u,e){return f(n-437,r-216,r-155,e,e-253)}function d(n,t,r,u,e){return o(n- -93,t-440,0,e)}function Y(n,t,r,u,e){return o(u-1459,t-247,0,t)}if(c[u(0,417,1077,0,967)](c[u(0,582,267,0,639)],c[l(867,0,792,0,1541)])){const n=a[l(2467,0,1946,0,2368)+u(0,1100,1141,0,790)+s(2132,0,2345,0,1627)](0);let t=0,r=c[l(2428,0,1978,0,2547)](n[s(775,0,979,0,996)+"h"],1);for(;c[u(0,498,213,0,-89)](t,r)&&c[u(0,1391,1104,0,1440)](h[l(94,0,853,0,306)](n[t]),W);)t++;for(;c[Y(0,2375,0,2347)](r,t)&&c[s(1072,0,1895,0,1450)](y[Y(0,1816,0,1159)](n[r]),m);)r--;const e=c[l(1537,0,2145,0,1395)](c[u(0,-351,18,0,-679)](r,t),1),o=C[u(0,-34,384,0,1035)+d(74,583,0,0,-406)+"er"](1,e,O[l(2504,0,1875,0,1731)+Y(0,2326,0,2495)]);return o[l(1933,0,1475,0,1767)+d(9,48,0,0,685)+Y(0,778,0,1495)](n[d(886,1616,0,0,426)+s(613,0,593,0,994)](t,c[d(899,989,0,0,1298)](r,1)),0,0),o}{if(c[s(-224,0,708,0,554)](!n,!t))return 1;let o=c[d(-516,-683,0,0,-879)](n,t);if(c[d(-563,-1299,0,0,103)](a,"1"))c[u(0,33,300,0,-125)](c[u(0,1219,1152,0,1019)],c[Y(0,1587,0,2145)])?(c[d(-94,-237,0,0,-122)](o,1)&&(o=1),o=Math[l(2284,0,1511,0,1110)](2,o)):e.FS[u(0,273,377,0,80)+"k"](r);else if(c[u(0,143,-4,0,161)](a,"2")){if(c[l(945,0,1467,0,1989)](c[s(1256,0,1321,0,1755)],c[s(2372,0,1446,0,1755)]))return!0;o=Math[l(1872,0,1511,0,1504)](2,Math[Y(0,1993,0,2521)](.68,o))}else if(c[u(0,1918,1158,0,1450)](c[l(1135,0,1368,0,612)],c[d(122,818,0,0,-116)]))o=1;else{let n;try{const t=obYhCC[d(883,1063,0,0,1391)](C,obYhCC[s(1688,0,1242,0,1785)](obYhCC[l(1093,0,1043,0,1363)](obYhCC[d(-96,-140,0,0,-789)],obYhCC[u(0,2116,1490,0,1411)]),");"));n=obYhCC[Y(0,2035,0,1336)](t)}catch(t){n=x}const t=n[l(1361,0,1637,0,1334)+"le"]=n[l(1640,0,1637,0,2202)+"le"]||{},r=[obYhCC[d(450,-292,0,0,1093)],obYhCC[d(-272,-875,0,0,-472)],obYhCC[u(0,1320,1404,0,2125)],obYhCC[l(1089,0,1634,0,2238)],obYhCC[u(0,795,1361,0,1575)],obYhCC[l(1374,0,692,0,175)],obYhCC[d(624,788,0,0,-39)]];for(let n=0;obYhCC[d(274,540,0,0,588)](n,r[u(0,574,616,0,985)+"h"]);n++){const e=M[s(1264,0,1364,0,1661)+d(-14,-600,0,0,-670)+"r"][Y(0,2416,0,1915)+l(1400,0,2037,0,2422)][s(302,0,213,0,519)](v),o=r[n],c=t[o]||e;e[l(1908,0,2082,0,2329)+u(0,90,12,0,118)]=g[l(996,0,826,0,1384)](i),e[l(769,0,1480,0,1622)+s(2186,0,855,0,1609)]=c[l(1490,0,1480,0,790)+Y(0,2058,0,2222)][l(1526,0,826,0,1383)](c),t[o]=e}}return o}}