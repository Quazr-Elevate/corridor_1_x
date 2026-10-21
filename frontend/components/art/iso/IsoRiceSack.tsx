import type { ArtProps } from "../tone";
import { ContactShadow, SW, SW_FINE, mapD, mix, onLeft, planeMatrix, qAt, rrectD, wpath, type P3 } from "./core";
import { IsoFrame } from "./IsoFrame";

/**
 * Jute sack, standing: a soft barrel body, a gathered top sewn along a
 * ridge with two ears, stencil "1121 BASMATI · 50 KG" laid onto the front face,
 * and a small lime grade tag tied at the right ear.
 */
export function IsoRiceSack(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id, surface }) => {
        const m = t.straw;
        const w = 50; // x
        const d = 34; // y
        const h = 58; // body height
        const rz = h + 13; // ridge height
        const b = 3.2; // bulge

        const FLt: P3 = [0, d, h];
        const FRt: P3 = [w, d, h];
        const BRt: P3 = [w, 0, h];
        const BLt: P3 = [0, 0, h];
        const FLb: P3 = [0, d, 0];
        const FRb: P3 = [w, d, 0];
        const BRb: P3 = [w, 0, 0];
        const RL: P3 = [-4, d / 2, rz + 1];
        const RR: P3 = [w + 4, d / 2, rz + 1];

        // shared control points so neighbouring faces meet exactly
        const cFront: P3 = [w / 2, d + b, h + 1];
        const cCorner: P3 = [w + b * 0.6, d + b * 0.6, h / 2];
        const cBottomF: P3 = [w / 2, d + b, -1.2];
        const cLeft: P3 = [-b * 0.6, d + b * 0.6, h / 2];
        const cEnd: P3 = [w + b, d / 2, h + 1];
        const cBackR: P3 = [w + b * 0.6, -b * 0.6, h / 2];
        const cBottomR: P3 = [w + b, d / 2, -1.2];
        const cShF: P3 = [w + 1, d * 0.8, h + 9];
        const cShB: P3 = [w + 1, d * 0.2, h + 9];
        const cRidge: P3 = [w / 2, d / 2 + 1.5, rz - 2.6];
        const cShFL: P3 = [-1, d * 0.8, h + 9];
        const cShBL: P3 = [-1, d * 0.2, h + 9];
        const cBack: P3 = [w / 2, -b, h + 1];

        const front = wpath([
          ["M", FLt],
          ["Q", cFront, FRt],
          ["Q", cCorner, FRb],
          ["Q", cBottomF, FLb],
          ["Q", cLeft, FLt],
          ["Z"],
        ]);
        const end = wpath([
          ["M", FRt],
          ["Q", cEnd, BRt],
          ["Q", cBackR, BRb],
          ["Q", cBottomR, FRb],
          ["Q", cCorner, FRt],
          ["Z"],
        ]);
        const shoulderFront = wpath([
          ["M", FLt],
          ["Q", cFront, FRt],
          ["Q", cShF, RR],
          ["Q", cRidge, RL],
          ["Q", cShFL, FLt],
          ["Z"],
        ]);
        const shoulderEnd = wpath([
          ["M", FRt],
          ["Q", cShF, RR],
          ["Q", cShB, BRt],
          ["Q", cEnd, FRt],
          ["Z"],
        ]);
        const shoulderBack = wpath([
          ["M", RL],
          ["Q", cRidge, RR],
          ["Q", cShB, BRt],
          ["Q", cBack, BLt],
          ["Q", cShBL, RL],
          ["Z"],
        ]);

        // stitches along the ridge seam, sitting just on the front shoulder
        const stitches: string[] = [];
        const N = 15;
        for (let i = 1; i < N; i++) {
          const p = qAt(RL, cRidge, RR, i / N);
          const a: P3 = [p[0] - 1.1, p[1] + 2.6, p[2] - 1.6];
          const c: P3 = [p[0] + 1.1, p[1] - 0.2, p[2] + 0.2];
          stitches.push(wpath([["M", a], ["L", c]]));
        }
        const seam = wpath([
          ["M", [RL[0] + 2, RL[1] + 1.3, RL[2] - 1]],
          ["Q", [cRidge[0], cRidge[1] + 1.3, cRidge[2] - 1], [RR[0] - 2, RR[1] + 1.3, RR[2] - 1]],
        ]);

        // ears: little gathered tufts past each end
        const earR = wpath([
          ["M", [w + 1, d / 2 + 2, rz - 1]],
          ["Q", [w + 6, d / 2 + 1, rz + 2], [w + 8.5, d / 2 - 0.5, rz + 4.5]],
          ["Q", [w + 5.5, d / 2 - 1, rz + 0.5], [w + 1.5, d / 2 - 2.5, rz - 2]],
          ["Z"],
        ]);
        const earL = wpath([
          ["M", [1, d / 2 + 2, rz - 1]],
          ["Q", [-4, d / 2 + 1, rz + 2], [-6.5, d / 2 - 0.5, rz + 4.5]],
          ["Q", [-3.5, d / 2 - 1, rz + 0.5], [0.5, d / 2 - 2.5, rz - 2]],
          ["Z"],
        ]);

        // jute weave on the front face
        const face = onLeft([0, d, h]);
        const weave: string[] = [];
        for (let v = 4; v < h - 2; v += 2.4) weave.push(`M1.5 ${v}H${w - 1.5}`);
        for (let u = 3; u < w - 1; u += 2.4) weave.push(`M${u} 2V${h - 2}`);

        const tagTop: P3 = [w + 5.5, d / 2 - 0.5, rz + 2.5];
        const ink = surface === "tower" ? "#EDEFEA" : "#0A0A0A";
        const textM = planeMatrix("left", [0, d + b * 0.75, h]);
        const shoulderFill = mix(m.top, m.left, 0.25);

        return (
          <g transform="translate(101 119) scale(1.25)">
            <defs>
              <clipPath id={id("front")}>
                <path d={front} />
              </clipPath>
            </defs>
            <ContactShadow c={[w / 2, d / 2]} rx={62} ry={27} gradId={id("sh")} dx={9} />
            <g stroke={m.edge} strokeWidth={SW / 1.25} strokeLinejoin="round">
              <path d={shoulderBack} fill={mix(m.top, m.right, 0.35)} />
              <path d={earL} fill={m.top} />
              <path d={end} fill={m.right} />
              <path d={front} fill={m.left} />
              <path d={shoulderEnd} fill={mix(m.top, m.right, 0.55)} />
              <path d={shoulderFront} fill={shoulderFill} />
              <path d={earR} fill={m.top} />
            </g>

            {/* weave + stencil */}
            <g clipPath={`url(#${id("front")})`}>
              <path d={mapD(weave.join(""), face)} stroke={m.mark} strokeOpacity={0.07} strokeWidth={0.6} />
            </g>
            <g transform={textM} fill={ink} fillOpacity={0.72}>
              <path
                d={rrectD(7, 15, w - 14, 25, 1.5)}
                fill="none"
                stroke={ink}
                strokeOpacity={0.55}
                strokeWidth={0.8}
                strokeDasharray="2.4 1.2"
              />
              <text
                x={w / 2}
                y={26}
                textAnchor="middle"
                fontSize={4.2}
                style={{ fontFamily: "var(--font-mono), 'Fragment Mono', ui-monospace, monospace" }}
              >
                1121 BASMATI
              </text>
              <text
                x={w / 2}
                y={33}
                textAnchor="middle"
                fontSize={3.1}
                fillOpacity={0.8}
                style={{ fontFamily: "var(--font-mono), 'Fragment Mono', ui-monospace, monospace" }}
              >
                50 KG · INDIA
              </text>
            </g>
            {/* crease shading near the corner */}
            <path
              d={wpath([
                ["M", [w - 6, d + 1.4, h - 6]],
                ["Q", [w - 3, d + 2.6, h / 2], [w - 6, d + 1.8, 8]],
              ])}
              fill="none"
              stroke={m.mark}
              strokeOpacity={0.14}
              strokeWidth={SW_FINE}
              strokeLinecap="round"
            />

            {/* seam + stitches */}
            <path d={seam} fill="none" stroke={m.mark} strokeOpacity={0.45} strokeWidth={0.7} />
            <g stroke={m.mark} strokeOpacity={0.75} strokeWidth={0.8} strokeLinecap="round">
              {stitches.map((s, i) => (
                <path key={i} d={s} />
              ))}
            </g>

            {/* lime grade tag on the right ear */}
            <path
              d={wpath([
                ["M", tagTop],
                ["Q", [w + 9, d / 2 - 3, rz - 2], [w + 9.5, d / 2 - 5, rz - 9]],
              ])}
              fill="none"
              stroke={m.edge}
              strokeWidth={0.7}
            />
            <g transform={planeMatrix("right", [w + 9.5, d / 2 - 2, rz - 8])}>
              <path
                d="M2.6 0H7.4L10 2.6V13.2C10 13.8 9.6 14.2 9 14.2H1C0.4 14.2 0 13.8 0 13.2V2.6Z"
                fill={t.lime.left}
                stroke={t.lime.edge}
                strokeWidth={0.8}
                strokeLinejoin="round"
              />
              <circle cx={5} cy={3.2} r={1} fill="none" stroke={t.lime.edge} strokeWidth={0.6} />
              <path d="M2.6 8.2H7.4M2.6 10.6H6" stroke={t.lime.edge} strokeWidth={0.7} strokeLinecap="round" />
            </g>
          </g>
        );
      }}
    </IsoFrame>
  );
}
