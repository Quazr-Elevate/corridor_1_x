import type { ArtProps } from "../tone";
import { Box, ContactShadow, SW_FINE, mapD, onLeft, wpath, iso, type P3 } from "./core";
import { ContainerUnit } from "./IsoContainerStack";
import { IsoFrame } from "./IsoFrame";
import { r2 } from "../ArtSvg";

/**
 * Ship-to-shore gantry crane: portal legs on travelling bogies, a long
 * boom reaching out over the water (+x), A-frame with stays, machinery
 * house on the back-reach, trolley + cab, and a container on the spreader.
 */
export function IsoCrane(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id }) => {
        const S = t.paper; // structure
        const legW = 4;
        const xs = [0, 44];
        const yBack = 0;
        const yFront = 34;
        const zTop = 74;
        const boomY = 15;
        const boomW = 8;
        const zBoom = 80;
        const apexTop: P3 = [2, boomY + boomW / 2, 114];
        const tip: P3 = [118, boomY + boomW / 2, zBoom + 6];
        const tail: P3 = [-46, boomY + boomW / 2, zBoom + 6];

        const bogie = (y: number) => <Box o={[-7, y - 1, 0]} s={[62, legW + 2, 6]} m={t.ink} />;
        const leg = (x: number, y: number) => <Box key={`${x}-${y}`} o={[x, y, 6]} s={[legW, legW, zTop - 6]} m={S} />;
        const portal = (y: number) => <Box o={[legW, y, 46]} s={[xs[1] - legW, legW, 5]} m={S} />;
        const brace = (y: number) => (
          <path
            d={mapD(`M${legW} 12L${xs[1]} 45M${xs[1]} 12L${legW} 45`, onLeft([0, y + legW, 51]))}
            stroke={S.edge}
            strokeWidth={SW_FINE}
            strokeLinecap="round"
          />
        );
        const lamp = iso(apexTop);

        return (
          <g transform="translate(112 130)">
            <ContactShadow c={[24, 20]} rx={84} ry={34} gradId={id("sh")} dx={10} />
            {/* rail lines on the quay */}
            <g stroke={t.paper.mark} strokeOpacity={0.14} strokeWidth={SW_FINE}>
              <path d={wpath([["M", [-34, yBack + 2, 0]], ["L", [86, yBack + 2, 0]]])} />
              <path d={wpath([["M", [-34, yFront + 2, 0]], ["L", [86, yFront + 2, 0]]])} />
            </g>

            {/* back frame */}
            {bogie(yBack)}
            {xs.map((x) => leg(x, yBack))}
            {portal(yBack)}

            {/* hanging load (behind the front frame in depth) */}
            <g>
              <path
                d={wpath([
                  ["M", [80, 19, 76]],
                  ["L", [80, 19, 35]],
                  ["M", [87, 19, 76]],
                  ["L", [87, 19, 35]],
                ])}
                stroke={S.edge}
                strokeWidth={0.7}
              />
              <Box o={[71, 13, 33]} s={[26, 12, 2.2]} m={t.ink} sw={0.9} />
              <ContainerUnit o={[72, 13.5, 20.5]} L={24} W={11} H={12.4} m={t.straw} t={t} />
            </g>

            {/* front frame */}
            {bogie(yFront)}
            {xs.map((x) => leg(x, yFront))}
            {portal(yFront)}
            {brace(yFront)}

            {/* top cross beams */}
            {xs.map((x) => (
              <Box key={x} o={[x - 1, yBack - 1, zTop]} s={[legW + 2, yFront + legW + 2, 6]} m={S} />
            ))}

            {/* trolley + operator cab (under the boom) */}
            <Box o={[77, boomY - 1, 76]} s={[13, boomW + 2, 4]} m={t.ink} sw={0.9} />
            <Box o={[73, boomY + 1, 67]} s={[7, 6, 9]} m={S} sw={0.9} />
            <path
              d={mapD("M0.8 1.6H5.6V5H0.8Z", onLeft([73.4, boomY + 7, 76]))}
              fill={t.ink.left}
              stroke="none"
            />

            {/* boom */}
            <Box o={[tail[0], boomY, zBoom]} s={[tip[0] - tail[0], boomW, 6]} m={S} />
            <path
              d={mapD(
                Array.from({ length: 27 }, (_, k) => {
                  const u = 3 + k * 6;
                  return `M${u} 0.6L${u + 3} 5.4L${u + 6} 0.6`;
                }).join(""),
                onLeft([tail[0], boomY + boomW, zBoom + 6]),
              )}
              fill="none"
              stroke={S.mark}
              strokeOpacity={0.28}
              strokeWidth={0.55}
              strokeLinejoin="round"
            />

            {/* machinery house on the back-reach */}
            <Box o={[-42, boomY - 3, zBoom + 6]} s={[22, boomW + 6, 11]} m={t.sand} />
            <path
              d={mapD("M3 3.5H19M3 6H19", onLeft([-42, boomY + boomW + 3, zBoom + 17]))}
              stroke={t.sand.mark}
              strokeOpacity={0.35}
              strokeWidth={0.6}
            />

            {/* A-frame */}
            <Box o={[0, boomY, zBoom + 6]} s={[4, 2.4, apexTop[2] - zBoom - 6]} m={S} />
            <Box o={[0, boomY + boomW - 2.4, zBoom + 6]} s={[4, 2.4, apexTop[2] - zBoom - 6]} m={S} />
            <Box o={[0, boomY, apexTop[2] - 3]} s={[4, boomW, 3]} m={S} sw={0.9} />

            {/* stays */}
            <path
              d={wpath([
                ["M", [3, boomY + 1, apexTop[2] - 1]],
                ["L", [tip[0] - 2, boomY + 1, tip[2]]],
                ["M", [3, boomY + boomW - 1, apexTop[2] - 1]],
                ["L", [tip[0] - 2, boomY + boomW - 1, tip[2]]],
                ["M", [1, boomY + boomW / 2, apexTop[2] - 1]],
                // backstay ends on the machinery-house roof, not through it
                ["L", [-21, boomY + boomW / 2, zBoom + 17]],
              ])}
              stroke={S.edge}
              strokeWidth={0.8}
              strokeLinecap="round"
            />

            {/* aviation lamp */}
            <circle cx={r2(lamp[0] + 1.7)} cy={r2(lamp[1] - 1.8)} r={2.1} fill={t.lime.left} stroke={t.lime.edge} strokeWidth={0.8} />
          </g>
        );
      }}
    </IsoFrame>
  );
}
