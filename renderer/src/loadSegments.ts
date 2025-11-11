import { Segment, segments } from "./generated/segments";

export { Segment };

export const loadSegments = (): Segment[] => segments.slice();
