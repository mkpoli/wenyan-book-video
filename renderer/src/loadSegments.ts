import { Segment, segments } from "./generated/segments";

export const loadSegments = (): Segment[] => segments.slice();
