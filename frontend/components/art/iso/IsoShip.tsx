import type { ArtProps, Material } from "../tone";
import { Box, FootprintShadow, SW, SW_FINE, mapD, mix, onLeft, poly, wpath, type P3 } from "./core";
import { IsoFrame } from "./IsoFrame";

/**
 * Container ship: solid hull with a raked bow, accommodation block and
 * funnel aft, five bays of containers on deck. Bow points to +x (lower
 * right), so the long side of the hull is the left face.
 */
export function IsoShip(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id }) => {
        const Lh = 164; // hull length to bow tip
        const B = 32; // beam
        const Hh = 20; // freeboard (waterline z = 0 → deck)
        const bow = 26; // bow taper length
        const hull = t.ink;
        const bowFace = mix(hull.left, hull.right, 0.55);

        // Deck outline, world coords at deck height.
        const deck: P3[] = [
          [0, 0, Hh],
          [Lh - bow, 0, Hh],
          [Lh, B / 2, Hh + 3],
          [Lh - bow, B, Hh],
          [0, B, Hh],
        ];

        // Bays of containers: x start, tiers, palette per tier.
        const tierH = 8.4;
        const bayL = 20;
        const bays: Array<{ x: number; tiers: Material[] }> = [
          { x: 30, tiers: [t.sand, t.paper, t.straw, t.sand] },
          { x: 51, tiers: [t.paper, t.ink, t.sand] },
          { x: 72, tiers: [t.straw, t.sand, t.paper, t.paper] },
          { x: 93, tiers: [t.sand, t.paper, t.ink] },
          { x: 114, tiers: [t.paper, t.straw] },
        ];
        const by0 = 2.5;
        const bw = B - 5;
        return (
          <g transform="translate(70 91)">
            <FootprintShadow
              points={[
                [-4, -2, 0],
                [Lh - bow, -2, 0],
                [Lh + 4, B / 2, 0],
                [Lh - bow, B + 6, 0],
                [-4, B + 6, 0],
              ]}
              filterId={id("soft")}
              color={t.shadow}
              opacity={t.shadowOpacity * 0.7}
              dx={7}
              dy={4}
            />

            {/* hull: long side + bow faces */}
            <g stroke={hull.edge} strokeWidth={SW} strokeLinejoin="round">
              <polygon
                points={poly([
                  [0, B, 0],
                  [Lh - bow, B, 0],
                  [Lh - bow, B, Hh],
                  [0, B, Hh],
                ])}
                fill={hull.left}
              />
              <polygon
                points={poly([
                  [Lh - bow, B, 0],
                  [Lh - 12, B / 2, 0],
                  [Lh, B / 2, Hh + 3],
                  [Lh - bow, B, Hh],
                ])}
                fill={bowFace}
              />
            </g>
            {/* boot-top (anti-fouling) band at the waterline + sheer line */}
            <g fill={t.amber} fillOpacity={0.9} stroke={hull.edge} strokeWidth={0.8} strokeLinejoin="round">
              <polygon
                points={poly([
                  [0, B, 0],
                  [Lh - bow, B, 0],
                  [Lh - bow, B, 3.4],
                  [0, B, 3.4],
                ])}
              />
              <polygon
                points={poly([
                  [Lh - bow, B, 0],
                  [Lh - 12, B / 2, 0],
                  [Lh - 11.4, B / 2, 3.4],
                  [Lh - bow, B, 3.4],
                ])}
              />
            </g>
            <path
              d={mapD(`M3 3.2H${Lh - bow}`, onLeft([0, B, Hh]))}
              stroke={hull.mark}
              strokeOpacity={0.18}
              strokeWidth={SW_FINE}
            />
            {/* deck */}
            <polygon points={poly(deck)} fill={hull.top} stroke={hull.edge} strokeWidth={SW} strokeLinejoin="round" />
            <polyline
              points={poly([
                [2, 2, Hh],
                [Lh - bow, 2, Hh],
                [Lh - 4, B / 2, Hh + 2.6],
                [Lh - bow, B - 2, Hh],
                [2, B - 2, Hh],
              ])}
              fill="none"
              stroke={hull.mark}
              strokeOpacity={0.16}
              strokeWidth={SW_FINE}
            />

            {/* accommodation block + bridge wings + funnel (aft) */}
            <Box o={[4, 5, Hh]} s={[22, B - 10, 34]} m={t.paper} />
            <path
              d={mapD(
                [6, 12.5, 19, 25.5].map((v) => `M2.5 ${v}H19.5`).join(""),
                onLeft([4, B - 5, Hh + 34]),
              )}
              stroke={t.paper.mark}
              strokeOpacity={0.55}
              strokeWidth={1.6}
              strokeDasharray="2.2 1.4"
            />
            <Box o={[3, 1, Hh + 34]} s={[24, B - 2, 4.5]} m={t.paper} />
            <path
              d={mapD("M2 2.2H22", onLeft([3, B - 1, Hh + 38.5]))}
              stroke={t.paper.mark}
              strokeOpacity={0.85}
              strokeWidth={1.4}
            />
            <Box o={[7, 12, Hh + 38.5]} s={[9, 10, 7.5]} m={t.ink} hideTop />
            <Box o={[7, 12, Hh + 46]} s={[9, 10, 2.6]} m={t.lime} sw={0.8} hideTop />
            <Box o={[7, 12, Hh + 48.6]} s={[9, 10, 3.4]} m={t.ink} />
            {/* mast */}
            <path
              d={wpath([
                ["M", [21, B / 2, Hh + 38.5]],
                ["L", [21, B / 2, Hh + 52]],
              ])}
              stroke={t.paper.edge}
              strokeWidth={SW_FINE}
              strokeLinecap="round"
            />
            <path
              d={wpath([
                ["M", [21, B / 2 - 4, Hh + 49]],
                ["L", [21, B / 2 + 4, Hh + 49]],
              ])}
              stroke={t.paper.edge}
              strokeWidth={SW_FINE}
              strokeLinecap="round"
            />
            {/* container bays (aft → forward = back → front in draw order) */}
            {bays.map((bay) =>
              bay.tiers.map((m, k) => (
                <g key={`${bay.x}-${k}`}>
                  <Box o={[bay.x, by0, Hh + k * tierH]} s={[bayL, bw, tierH]} m={m} sw={0.9} />
                  {/* row dividers on the top of the uppermost tier */}
                  {k === bay.tiers.length - 1
                    ? [1, 2, 3].map((r) => (
                        <polyline
                          key={r}
                          points={poly([
                            [bay.x + 0.6, by0 + (bw / 4) * r, Hh + (k + 1) * tierH],
                            [bay.x + bayL - 0.6, by0 + (bw / 4) * r, Hh + (k + 1) * tierH],
                          ])}
                          stroke={m.mark}
                          strokeOpacity={0.22}
                          strokeWidth={0.6}
                        />
                      ))
                    : null}
                  {/* ribs on the long face */}
                  <path
                    d={mapD(
                      Array.from({ length: 6 }, (_, i) => `M${2 + i * 3.4} 1.4V${tierH - 1.4}`).join(""),
                      onLeft([bay.x, by0 + bw, Hh + (k + 1) * tierH]),
                    )}
                    stroke={m.mark}
                    strokeOpacity={m === t.ink ? 0.14 : 0.18}
                    strokeWidth={0.55}
                  />
                </g>
              )),
            )}

          </g>
        );
      }}
    </IsoFrame>
  );
}
