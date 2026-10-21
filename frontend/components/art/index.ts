/**
 * components/art — photography and the drawn library.
 *
 *   import { Photo, CommodityArt, CorridorMap } from "@/components/art";
 *
 * Photography first (`Photo`, `AmbientPhoto`, with `lib/media`); the drawn
 * pieces are fallbacks and diagrams:
 *   • CommodityArt — macro still-life for categories without a photo.
 *   • CorridorMap  — India ⇄ UAE dotted map with ports and sea lanes.
 *   • Iso*         — isometric objects (container stack, ship, sack, heap,
 *                    warehouse, crane) for empty states and explainers.
 * See app/gallery (dev only) for every piece on both surfaces.
 */

export { Photo, PhotoThumb, PORTRAIT_MEDIA, type PhotoProps } from "./Photo";
export { AmbientPhoto } from "./AmbientPhoto";

export { CommodityArt, ART_CATEGORIES, artCategory, type ArtCategory } from "./CommodityArt";
export { CorridorMap, type CorridorMapProps } from "./CorridorMap";
export { PORTS, DEFAULT_LANES, type Port, type PortId, type Lane } from "./map/geo";

export { IsoContainerStack } from "./iso/IsoContainerStack";
export { IsoShip } from "./iso/IsoShip";
export { IsoRiceSack } from "./iso/IsoRiceSack";
export { IsoGrainHeap } from "./iso/IsoGrainHeap";
export { IsoWarehouse } from "./iso/IsoWarehouse";
export { IsoCrane } from "./iso/IsoCrane";

export { ArtSvg, useArtId } from "./ArtSvg";
export type { ArtProps, Surface } from "./tone";
