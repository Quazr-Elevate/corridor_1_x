import type { ArtProps } from "../tone";
import { Box, ContactShadow, SW, SW_FINE, circleD, mapD, mix, onLeft, onRight, poly, rrectD } from "./core";
import { IsoFrame } from "./IsoFrame";

/**
 * Bonded warehouse: long shed with a shallow gable roof (ridge along x),
 * standing-seam cladding, three dock doors on a loading apron, a gable
 * door with a lime lamp over it.
 */
export function IsoWarehouse(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id }) => {
        const L = 128; // x
        const D = 62; // y
        const Hw = 36; // eave height
        const Hr = 15; // ridge rise
        const o = 3; // roof overhang
        const wall = t.paper;
        const roof = t.sand;
        const ridgeY = D / 2;

        const roofBack = poly([
          [-o, ridgeY, Hw + Hr],
          [L + o, ridgeY, Hw + Hr],
          [L + o, -o, Hw - 1],
          [-o, -o, Hw - 1],
        ]);
        const roofFront = poly([
          [-o, ridgeY, Hw + Hr],
          [L + o, ridgeY, Hw + Hr],
          [L + o, D + o, Hw - 1],
          [-o, D + o, Hw - 1],
        ]);
        const fascia = poly([
          [-o, D + o, Hw - 1],
          [L + o, D + o, Hw - 1],
          [L + o, D + o, Hw - 3.2],
          [-o, D + o, Hw - 3.2],
        ]);
        const fasciaEnd = poly([
          [L + o, D + o, Hw - 1],
          [L + o, ridgeY, Hw + Hr],
          [L + o, -o, Hw - 1],
          [L + o, -o, Hw - 3.2],
          [L + o, ridgeY, Hw + Hr - 2.2],
          [L + o, D + o, Hw - 3.2],
        ]);
        const gable = poly([
          [L, 0, 0],
          [L, D, 0],
          [L, D, Hw],
          [L, ridgeY, Hw + Hr],
          [L, 0, Hw],
        ]);
        const side = poly([
          [0, D, 0],
          [L, D, 0],
          [L, D, Hw],
          [0, D, Hw],
        ]);

        // standing seams on the front roof plane (eave → ridge)
        const seams: string[] = [];
        for (let x = 6; x < L; x += 7) {
          seams.push(poly([[x, D + o - 0.5, Hw - 1], [x, ridgeY + 0.4, Hw + Hr]]));
        }
        // cladding ribs on the long wall
        const wallFace = onLeft([0, D, Hw]);
        const ribs: string[] = [];
        for (let u = 3; u < L; u += 3) ribs.push(`M${u} 7V${Hw - 0.5}`);
        const doors = [18, 52, 86];
        const dock = 7;

        const gableFace = onRight([L, D, Hw]);
        // height of the front roof plane at a given y (eave → ridge), lifted a hair
        const zRoof = (y: number) => Hw - 1 + ((D + o - y) / (D + o - ridgeY)) * (Hr + 1) + 0.15;
        const darkGlass = t.ink.left;

        return (
          <g transform="translate(82 50)">
            <ContactShadow c={[L / 2, D / 2 + 6]} rx={128} ry={50} gradId={id("sh")} dx={10} />
            {/* loading apron */}
            <Box o={[-2, D, 0]} s={[L + 2, dock, 3.2]} m={t.sand} sw={0.9} />

            <g stroke={wall.edge} strokeWidth={SW} strokeLinejoin="round">
              <polygon points={side} fill={wall.left} />
              <polygon points={gable} fill={wall.right} />
            </g>
            {/* wall ribs (masked around doors by drawing doors over them) */}
            <path d={mapD(ribs.join(""), wallFace)} stroke={wall.mark} strokeOpacity={0.11} strokeWidth={0.6} />
            {/* clerestory band */}
            <path
              d={mapD(`M4 3.2H${L - 4}`, wallFace)}
              stroke={darkGlass}
              strokeWidth={2.6}
              strokeLinecap="butt"
              strokeDasharray="9 2"
            />
            {/* dock doors: roller shutters */}
            {doors.map((u) => (
              <g key={u}>
                <path
                  d={mapD(`M${u} ${Hw}V${Hw - 22}H${u + 20}V${Hw}`, wallFace)}
                  fill={mix(wall.left, wall.right, 0.6)}
                  stroke={wall.edge}
                  strokeWidth={SW_FINE}
                  strokeLinejoin="round"
                />
                <path
                  d={mapD(
                    Array.from({ length: 9 }, (_, k) => `M${u + 0.6} ${Hw - 20 + k * 2.3}H${u + 19.4}`).join(""),
                    wallFace,
                  )}
                  stroke={wall.mark}
                  strokeOpacity={0.22}
                  strokeWidth={0.5}
                />
                {/* dock bumpers */}
                <path
                  d={mapD(`M${u - 1.6} ${Hw - 4}V${Hw - 0.5}M${u + 21.6} ${Hw - 4}V${Hw - 0.5}`, wallFace)}
                  stroke={t.ink.left}
                  strokeWidth={1.8}
                  strokeLinecap="round"
                />
              </g>
            ))}
            {/* personnel door + window */}
            <path
              d={mapD(rrectD(L - 14, Hw - 15, 7, 15, 0.4), wallFace)}
              fill={mix(wall.left, wall.right, 0.6)}
              stroke={wall.edge}
              strokeWidth={SW_FINE}
            />

            {/* gable: big door, vents, lime lamp */}
            <path
              d={mapD(`M14 ${Hw}V${Hw - 26}H${D - 14}V${Hw}`, gableFace)}
              fill={mix(wall.right, t.ink.left, 0.12)}
              stroke={wall.edge}
              strokeWidth={SW_FINE}
              strokeLinejoin="round"
            />
            <path
              d={mapD(
                Array.from({ length: 11 }, (_, k) => `M14.6 ${Hw - 24 + k * 2.3}H${D - 14.6}`).join(""),
                gableFace,
              )}
              stroke={wall.mark}
              strokeOpacity={0.2}
              strokeWidth={0.5}
            />
            <path
              d={mapD(
                [-4.5, -1.5, 1.5, 4.5].map((dv) => `M${D / 2 - 5} ${-6 + dv * 0.6}H${D / 2 + 5}`).join(""),
                gableFace,
              )}
              stroke={wall.mark}
              strokeOpacity={0.5}
              strokeWidth={0.8}
            />
            <path d={mapD(rrectD(D / 2 - 6.5, -10, 13, 8, 1), gableFace)} fill="none" stroke={wall.edge} strokeWidth={SW_FINE} />
            <path d={mapD(circleD(D / 2, Hw - 29.6, 1.7), gableFace)} fill={t.lime.left} stroke={t.lime.edge} strokeWidth={0.7} />
            <path d={mapD(`M${D / 2 - 3.4} ${Hw - 31.8}H${D / 2 + 3.4}`, gableFace)} stroke={wall.edge} strokeWidth={0.9} strokeLinecap="round" />

            {/* roof */}
            <g stroke={roof.edge} strokeWidth={SW} strokeLinejoin="round">
              <polygon points={roofBack} fill={roof.right} />
              <polygon points={fasciaEnd} fill={mix(roof.left, roof.right, 0.6)} />
              <polygon points={roofFront} fill={roof.top} />
              <polygon points={fascia} fill={roof.left} />
            </g>
            <g stroke={roof.mark} strokeOpacity={0.16} strokeWidth={0.6}>
              {seams.map((p, i) => (
                <polyline key={i} points={p} fill="none" />
              ))}
            </g>
            {/* ridge vent + skylights */}
            <Box o={[22, ridgeY - 2.5, Hw + Hr - 0.4]} s={[L - 44, 5, 2.4]} m={roof} sw={0.9} />
            {[16, 50, 84].map((x) => (
              <polygon
                key={x}
                points={poly([
                  [x, D - 8, zRoof(D - 8)],
                  [x + 18, D - 8, zRoof(D - 8)],
                  [x + 18, D - 20, zRoof(D - 20)],
                  [x, D - 20, zRoof(D - 20)],
                ])}
                fill={mix(roof.top, t.paper.top, 0.6)}
                stroke={roof.edge}
                strokeWidth={SW_FINE}
                strokeLinejoin="round"
              />
            ))}
          </g>
        );
      }}
    </IsoFrame>
  );
}
