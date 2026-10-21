import type { ArtProps, IsoTone, Material } from "../tone";
import { Box, SW_FINE, mapD, onLeft, onRight, poly, rrectD, ContactShadow, type P3 } from "./core";
import { IsoFrame } from "./IsoFrame";

/**
 * One shipping container. Length runs along +x, so the long corrugated
 * side is the LEFT face and the door end is the RIGHT face.
 */
export function ContainerUnit({
  o,
  L,
  W,
  H,
  m,
  t,
  seal,
}: {
  o: P3;
  L: number;
  W: number;
  H: number;
  m: Material;
  t: IsoTone;
  /** Draw the lime door seal on this container. */
  seal?: boolean;
}) {
  const [x, y, z] = o;
  const onInk = m === t.ink;
  const k = onInk ? 0.8 : 1; // marks read a touch quieter on solid faces
  const side = onLeft([x, y + W, z + H]);
  const door = onRight([x + L, y + W, z + H]);

  const ribs: string[] = [];
  for (let u = 4.4; u < L - 4; u += 3.3) {
    ribs.push(`M${u} 2.2V${H - 2.2}M${u + 1.15} 2.2V${H - 2.2}`);
  }
  const bars = [0.17, 0.37, 0.63, 0.83].map((f) => f * W);
  const roof: string[] = [];
  for (let u = 6; u < L - 3; u += 6) roof.push(poly([[x + u, y + 1.2, z + H], [x + u, y + W - 1.2, z + H]]));

  return (
    <g>
      <Box o={o} s={[L, W, H]} m={m} />
      {/* roof ribs */}
      {roof.map((p, i) => (
        <polyline key={i} points={p} fill="none" stroke={m.mark} strokeOpacity={0.1 * k} strokeWidth={SW_FINE} />
      ))}
      {/* long side: rails, posts, corrugation */}
      <path
        d={mapD(`M1.8 0V${H}M${L - 1.8} 0V${H}M0 1.9H${L}M0 ${H - 1.9}H${L}`, side)}
        fill="none"
        stroke={m.mark}
        strokeOpacity={0.32 * k}
        strokeWidth={SW_FINE}
      />
      <path d={mapD(ribs.join(""), side)} fill="none" stroke={m.mark} strokeOpacity={0.16 * k} strokeWidth={0.6} />
      {/* door end */}
      <path
        d={mapD(rrectD(1.5, 1.6, W - 3, H - 3.2, 0.6), door)}
        fill="none"
        stroke={m.mark}
        strokeOpacity={0.35 * k}
        strokeWidth={SW_FINE}
      />
      <path d={mapD(`M${W / 2} 1.6V${H - 1.6}`, door)} stroke={m.mark} strokeOpacity={0.55 * k} strokeWidth={SW_FINE} />
      <path
        d={mapD(
          bars
            .map(
              (u) =>
                `M${u} 2.8V${H - 2.8}M${u - 0.9} 2.8H${u + 0.9}M${u - 0.9} ${H - 2.8}H${u + 0.9}` +
                `M${u} ${H * 0.56}H${u + (u < W / 2 ? 2 : -2)}`,
            )
            .join(""),
          door,
        )}
        fill="none"
        stroke={m.mark}
        strokeOpacity={0.55 * k}
        strokeWidth={SW_FINE}
        strokeLinecap="round"
      />
      {/* corner castings */}
      <path
        d={mapD(
          [
            [0.4, 0.4],
            [W - 2.2, 0.4],
            [0.4, H - 2.2],
            [W - 2.2, H - 2.2],
          ]
            .map(([u, v]) => `M${u} ${v}H${u + 1.8}V${v + 1.8}H${u}Z`)
            .join(""),
          door,
        )}
        fill={m.mark}
        fillOpacity={0.4 * k}
      />
      {seal ? (
        <g>
          <path
            d={mapD(`M${bars[2] - 0.2} ${H * 0.56 - 0.4}C${bars[2] - 1.6} ${H * 0.56 + 2} ${bars[2] - 1.4} ${H * 0.56 + 3.6} ${bars[2] - 0.6} ${H * 0.56 + 4.4}`, door)}
            fill="none"
            stroke={m.mark}
            strokeOpacity={0.7}
            strokeWidth={0.6}
          />
          <path
            d={mapD(rrectD(bars[2] - 2.1, H * 0.56 + 4.2, 3, 4.4, 0.7), door)}
            fill={t.lime.left}
            stroke={t.lime.edge}
            strokeWidth={0.7}
            strokeLinejoin="round"
          />
        </g>
      ) : null}
    </g>
  );
}

/**
 * Five containers in a yard stack: a two-high back row, a 40ft + 20ft
 * middle row and a solid front unit pulled forward, carrying the lime
 * door seal.
 */
export function IsoContainerStack(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id }) => {
        const L = 76;
        const W = 30;
        const H = 30;
        const g = 1.6;
        const y1 = W + g;
        const y2 = 2 * (W + g);
        const units: Array<{ o: P3; L: number; m: Material; seal?: boolean }> = [
          { o: [0, 0, 0], L, m: t.sand },
          { o: [0, 0, H], L, m: t.straw },
          { o: [0, y1, 0], L, m: t.paper },
          { o: [L - 37, y1, H], L: 37, m: t.sand },
          { o: [14, y2, 0], L, m: t.ink, seal: true },
        ];
        return (
          <g transform="translate(118 78)">
            <ContactShadow c={[46, 48]} rx={112} ry={46} gradId={id("sh")} dx={12} />
            {units.map((u, i) => (
              <ContainerUnit key={i} o={u.o} L={u.L} W={W} H={H} m={u.m} t={t} seal={u.seal} />
            ))}
          </g>
        );
      }}
    </IsoFrame>
  );
}
