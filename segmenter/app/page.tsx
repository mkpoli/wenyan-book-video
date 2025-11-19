'use client';

import { useState, useCallback, useMemo } from 'react';
import SegmentsLoader from './components/SegmentsLoader';
import TextPane from './components/TextPane';
import type { ChapterSentences } from './api/sentences/[chapterId]/route';
import type { ChapterSegments } from './components/SegmentsLoader';
import type { BoundaryOperation } from './utils/segmentOperations';
import {
  computeSegments,
  getIdChangeMap,
  getModifiedSegmentIds,
  getInitialBoundaries,
} from './utils/segmentOperations';

import SegmentPreview from './components/SegmentPreview';

export default function Home() {
  const [sentences, setSentences] = useState<ChapterSentences | null>(null);
  const [originalSegments, setOriginalSegments] = useState<ChapterSegments | null>(null);
  const [operations, setOperations] = useState<BoundaryOperation[]>([]);
  const [operationHistoryIndex, setOperationHistoryIndex] = useState<number>(-1);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);

  // Compute current segments from original + operations
  const segments = useMemo(() => {
    if (!originalSegments || !sentences) return null;
    const currentOps = operations.slice(0, operationHistoryIndex + 1);
    return computeSegments(originalSegments, currentOps, sentences);
  }, [originalSegments, operations, operationHistoryIndex, sentences]);

  // Compute ID changes and modifications
  const { segmentIdChanges, modifiedSegmentIds } = useMemo(() => {
    if (!originalSegments || !segments) {
      return {
        segmentIdChanges: new Map<string, string>(),
        modifiedSegmentIds: new Set<string>(),
      };
    }
    return {
      segmentIdChanges: getIdChangeMap(originalSegments, segments),
      modifiedSegmentIds: getModifiedSegmentIds(originalSegments, segments),
    };
  }, [originalSegments, segments]);

  const handleDataLoad = useCallback(
    (loadedSentences: ChapterSentences | null, loadedSegments: ChapterSegments | null) => {
      setSentences(loadedSentences);
      if (loadedSegments) {
        setOriginalSegments(JSON.parse(JSON.stringify(loadedSegments)));
        setOperations([]);
        setOperationHistoryIndex(-1);
      }
    },
    []
  );

  const handleSegmentClick = useCallback((segmentId: string) => {
    setSelectedSegmentId(segmentId);
  }, []);

  const handleBoundaryToggle = useCallback(
    (sentenceIndex: number, hasBoundary: boolean) => {
      if (!sentences || !originalSegments) return;

      const operation: BoundaryOperation = {
        type: hasBoundary ? 'merge' : 'split',
        sentenceIndex,
        timestamp: Date.now(),
      };

      // Remove operations after current index (for redo handling)
      const newOperations = operations.slice(0, operationHistoryIndex + 1);
      newOperations.push(operation);

      setOperations(newOperations);
      setOperationHistoryIndex(newOperations.length - 1);
    },
    [sentences, originalSegments, operations, operationHistoryIndex]
  );

  const handleUndo = useCallback(() => {
    if (operationHistoryIndex >= 0) {
      setOperationHistoryIndex(operationHistoryIndex - 1);
    }
  }, [operationHistoryIndex]);

  const handleRedo = useCallback(() => {
    if (operationHistoryIndex < operations.length - 1) {
      setOperationHistoryIndex(operationHistoryIndex + 1);
    }
  }, [operationHistoryIndex, operations.length]);

  const handleSave = useCallback(async (): Promise<{ success: boolean; error?: string }> => {
    if (!segments || !originalSegments) {
      return { success: false, error: 'No segments to save' };
    }

    try {
      const response = await fetch(`/api/segments/${segments.chapterId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(segments),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to save segments');
      }

      // After saving, update original segments to the current state
      // This resets the "modified" state
      setOriginalSegments(JSON.parse(JSON.stringify(segments)));
      setOperations([]);
      setOperationHistoryIndex(-1);

      return { success: true };
    } catch (error) {
      console.error('Save error:', error);
      return { success: false, error: error instanceof Error ? error.message : 'Unknown error' };
    }
  }, [segments, originalSegments]);

  return (
    <div className="flex h-screen bg-zinc-50 font-sans dark:bg-black">
      {/* Left sidebar */}
      <aside className="w-80 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-black flex flex-col">
        <SegmentsLoader
          onDataLoad={handleDataLoad}
          onSegmentClick={handleSegmentClick}
          selectedSegmentId={selectedSegmentId}
          externalSegments={segments}
          segmentIdChanges={segmentIdChanges}
          modifiedSegmentIds={modifiedSegmentIds}
        />
      </aside>

      {/* Main content area - Preview on top, editing below */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Preview panel at top */}
        <div className="h-120 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-black flex flex-col shrink-0">
          <SegmentPreview
            sentences={sentences}
            segments={segments}
            selectedSegmentId={selectedSegmentId}
            onSegmentClick={handleSegmentClick}
          />
        </div>

        {/* Text editing panel below */}
        <div className="flex-1 overflow-hidden custom-scrollbar">
          <TextPane
            sentences={sentences}
            segments={segments}
            selectedSegmentId={selectedSegmentId}
            onBoundaryToggle={handleBoundaryToggle}
            onSegmentClick={handleSegmentClick}
            originalSegments={originalSegments}
            segmentIdChanges={segmentIdChanges}
            modifiedSegmentIds={modifiedSegmentIds}
            canUndo={operationHistoryIndex >= 0}
            canRedo={operationHistoryIndex < operations.length - 1}
            hasUnsavedChanges={operations.length > 0}
            onUndo={handleUndo}
            onRedo={handleRedo}
            onSave={handleSave}
          />
        </div>
      </main>
    </div>
  );
}
