import type { Segment, ChapterSegments } from '../components/SegmentsLoader';
import type { ChapterSentences } from '../api/sentences/[chapterId]/route';

export type OperationType = 'split' | 'merge';

export interface BoundaryOperation {
  type: OperationType;
  sentenceIndex: number; // The sentence index where the boundary is (between sentenceIndex and sentenceIndex+1)
  timestamp: number;
}

/**
 * Get initial boundaries from original segments
 */
export function getInitialBoundaries(segments: ChapterSegments, sentences: ChapterSentences): Set<number> {
  const boundaries = new Set<number>();
  const sentenceIndexMap = new Map<string, number>();

  sentences.sentences.forEach((sentence, idx) => {
    sentenceIndexMap.set(sentence.id, idx);
  });

  segments.segments.forEach((segment) => {
    if (segment.sentenceIds.length > 0) {
      const firstIdx = sentenceIndexMap.get(segment.sentenceIds[0]);
      if (firstIdx !== undefined) {
        boundaries.add(firstIdx);
      }
    }
  });

  return boundaries;
}

/**
 * Compute current boundaries from original boundaries + operations
 */
export function computeBoundaries(originalBoundaries: Set<number>, operations: BoundaryOperation[]): Set<number> {
  const boundaries = new Set(originalBoundaries);

  operations.forEach((op) => {
    if (op.type === 'split') {
      // Add boundary (if not already present)
      boundaries.add(op.sentenceIndex);
    } else if (op.type === 'merge') {
      // Remove boundary (if present)
      boundaries.delete(op.sentenceIndex);
    }
  });

  return boundaries;
}

/**
 * Build segments from boundaries and sentences
 */
export function buildSegmentsFromBoundaries(
  boundaries: Set<number>,
  sentences: ChapterSentences,
  originalSegments: ChapterSegments
): ChapterSegments {
  const segments: Segment[] = [];
  const sentenceIndexMap = new Map<string, number>();

  sentences.sentences.forEach((sentence, idx) => {
    sentenceIndexMap.set(sentence.id, idx);
  });

  const boundaryArray = Array.from(boundaries).sort((a, b) => a - b);

  // Ensure first boundary is at index 0
  if (boundaryArray.length === 0 || boundaryArray[0] !== 0) {
    boundaryArray.unshift(0);
  }

  for (let i = 0; i < boundaryArray.length; i++) {
    const startIdx = boundaryArray[i];
    const endIdx = i < boundaryArray.length - 1 ? boundaryArray[i + 1] : sentences.sentences.length;

    const sentenceIds: string[] = [];
    for (let j = startIdx; j < endIdx; j++) {
      sentenceIds.push(sentences.sentences[j].id);
    }

    if (sentenceIds.length > 0) {
      const segmentIndex = i + 1;
      const chapterNumber = originalSegments.chapterNumber;

      // Try to find matching original segment to preserve metadata
      const matchingOriginal = originalSegments.segments.find((seg) => seg.sentenceIds[0] === sentenceIds[0]);

      const segment: Segment = {
        id: `${chapterNumber}-${segmentIndex}`,
        chapterId: originalSegments.chapterId,
        segmentIndex,
        sentenceIds,
        isCodeBlock: matchingOriginal?.isCodeBlock || false,
        // isListItem: matchingOriginal?.isListItem || false,
      };

      // If this segment spans multiple original segments, check if any are code blocks/list items
      const originalSegsForRange = originalSegments.segments.filter((seg) =>
        seg.sentenceIds.some((id) => sentenceIds.includes(id))
      );
      if (originalSegsForRange.length > 0) {
        segment.isCodeBlock = originalSegsForRange.some((seg) => seg.isCodeBlock);
        // segment.isListItem = originalSegsForRange.some((seg) => seg.isListItem);
      }

      segments.push(segment);
    }
  }

  return {
    ...originalSegments,
    segments,
  };
}

/**
 * Compute current segments from original segments + operations
 */
export function computeSegments(
  originalSegments: ChapterSegments,
  operations: BoundaryOperation[],
  sentences: ChapterSentences
): ChapterSegments {
  const originalBoundaries = getInitialBoundaries(originalSegments, sentences);
  const currentBoundaries = computeBoundaries(originalBoundaries, operations);
  return buildSegmentsFromBoundaries(currentBoundaries, sentences, originalSegments);
}

/**
 * Check if there's a boundary at a given sentence index
 */
export function hasBoundaryAt(
  sentenceIndex: number,
  originalBoundaries: Set<number>,
  operations: BoundaryOperation[]
): boolean {
  const boundaries = computeBoundaries(originalBoundaries, operations);
  return boundaries.has(sentenceIndex);
}

/**
 * Get ID change map comparing original segments to computed segments
 */
export function getIdChangeMap(
  originalSegments: ChapterSegments,
  computedSegments: ChapterSegments
): Map<string, string> {
  const changes = new Map<string, string>();
  const originalMap = new Map<string, Segment>();

  originalSegments.segments.forEach((seg) => {
    if (seg.sentenceIds.length > 0) {
      originalMap.set(seg.sentenceIds[0], seg);
    }
  });

  computedSegments.segments.forEach((computedSeg) => {
    if (computedSeg.sentenceIds.length > 0) {
      const originalSeg = originalMap.get(computedSeg.sentenceIds[0]);
      if (originalSeg && originalSeg.id !== computedSeg.id) {
        changes.set(originalSeg.id, computedSeg.id);
      }
    }
  });

  return changes;
}

/**
 * Get modified segment IDs
 */
export function getModifiedSegmentIds(
  originalSegments: ChapterSegments,
  computedSegments: ChapterSegments
): Set<string> {
  const modified = new Set<string>();
  const originalMap = new Map<string, Set<string>>();

  originalSegments.segments.forEach((seg) => {
    const key = seg.sentenceIds.join(',');
    if (!originalMap.has(key)) {
      originalMap.set(key, new Set());
    }
    originalMap.get(key)!.add(seg.id);
  });

  computedSegments.segments.forEach((computedSeg) => {
    const key = computedSeg.sentenceIds.join(',');
    const originalIds = originalMap.get(key);

    // If this exact sentence set doesn't exist in original, it's modified
    // If it exists, even if ID changed, it's just renumbered (not modified)
    if (!originalIds) {
      modified.add(computedSeg.id);
    }
  });

  return modified;
}
