'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import type { Sentence, ChapterSentences } from '../api/sentences/[chapterId]/route';
import type { Segment, ChapterSegments } from './SegmentsLoader';
import { Icon } from '@iconify/react';

interface TextPaneProps {
  sentences: ChapterSentences | null;
  segments: ChapterSegments | null;
  selectedSegmentId?: string | null;
  onBoundaryToggle?: (sentenceIndex: number, hasBoundary: boolean) => void;
  onSegmentClick?: (segmentId: string) => void;
  originalSegments?: ChapterSegments | null;
  segmentIdChanges?: Map<string, string>;
  modifiedSegmentIds?: Set<string>;
  canUndo?: boolean;
  canRedo?: boolean;
  hasUnsavedChanges?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  onSave?: () => Promise<{ success: boolean; error?: string }>;
}

export default function TextPane({
  sentences,
  segments,
  selectedSegmentId,
  onBoundaryToggle,
  onSegmentClick,
  originalSegments,
  segmentIdChanges = new Map(),
  modifiedSegmentIds = new Set(),
  canUndo = false,
  canRedo = false,
  hasUnsavedChanges = false,
  onUndo,
  onRedo,
  onSave,
}: TextPaneProps) {
  const [hoveredBoundary, setHoveredBoundary] = useState<number | null>(null);
  const [currentSegmentId, setCurrentSegmentId] = useState<string | null>(null);
  const [lastChangedBoundary, setLastChangedBoundary] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const sentenceRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll to segment when selectedSegmentId changes
  useEffect(() => {
    if (!selectedSegmentId || !segments || !sentences) return;

    const segment = segments.segments.find((s) => s.id === selectedSegmentId);
    if (!segment || segment.sentenceIds.length === 0) return;

    // Get the first sentence ID of the segment
    const firstSentenceId = segment.sentenceIds[0];
    const element = sentenceRefs.current.get(firstSentenceId);

    if (element && containerRef.current) {
      // Scroll the sentence into view
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
      // Also update current segment for highlighting
      setCurrentSegmentId(selectedSegmentId);
    }
  }, [selectedSegmentId, segments, sentences]);

  // Build maps for efficient lookup
  const { sentenceIndexMap, segmentBoundaries, sentenceToSegment, blockBoundaries, blockIdMap } = useMemo(() => {
    if (!sentences || !segments) {
      return {
        sentenceIndexMap: new Map<string, number>(),
        segmentBoundaries: new Set<number>(),
        sentenceToSegment: new Map<string, string>(),
        blockBoundaries: new Set<number>(),
        blockIdMap: new Map<string, string>(),
      };
    }

    const indexMap = new Map<string, number>();
    sentences.sentences.forEach((sentence, idx) => {
      indexMap.set(sentence.id, idx);
    });

    const boundaries = new Set<number>();
    const sentToSeg = new Map<string, string>();
    const segmentIdMap = new Map<string, Segment>();

    segments.segments.forEach((segment) => {
      segmentIdMap.set(segment.id, segment);
      segment.sentenceIds.forEach((sentenceId) => {
        sentToSeg.set(sentenceId, segment.id);
      });

      // Mark boundaries: the first sentence of each segment (including the very first at index 0)
      if (segment.sentenceIds.length > 0) {
        const firstIdx = indexMap.get(segment.sentenceIds[0]);
        if (firstIdx !== undefined) {
          boundaries.add(firstIdx);
        }
      }
    });

    // Calculate block boundaries from blockId
    const blockBoundariesSet = new Set<number>();
    const blockIdMapLocal = new Map<string, string>();
    let prevBlockId: string | null = null;

    sentences.sentences.forEach((sentence, idx) => {
      const blockId = sentence.blockId || '';
      blockIdMapLocal.set(sentence.id, blockId);

      if (idx === 0 || (blockId && blockId !== prevBlockId)) {
        blockBoundariesSet.add(idx);
      }
      prevBlockId = blockId;
    });

    return {
      sentenceIndexMap: indexMap,
      segmentBoundaries: boundaries,
      sentenceToSegment: sentToSeg,
      segmentIdMap,
      blockBoundaries: blockBoundariesSet,
      blockIdMap: blockIdMapLocal,
    };
  }, [sentences, segments]);

  // Get segment info for a sentence
  const getSegmentForSentence = (sentenceId: string): Segment | null => {
    const segmentId = sentenceToSegment.get(sentenceId);
    if (!segmentId || !segments) return null;
    return segments.segments.find((s) => s.id === segmentId) || null;
  };

  // Check if there's a segment boundary after sentence index (i.e., next sentence starts a new segment)
  const hasSegmentBoundary = (sentenceIndex: number): boolean => {
    return segmentBoundaries.has(sentenceIndex + 1);
  };

  // Get segment label for boundary (shown before the next sentence which starts a new segment)
  const getBoundaryLabel = (sentenceIndex: number): { label: string; oldId?: string } | null => {
    if (!sentences || !hasSegmentBoundary(sentenceIndex)) return null;
    const nextSentenceIndex = sentenceIndex + 1;
    const nextSentenceId = sentences.sentences[nextSentenceIndex]?.id;
    if (!nextSentenceId) return null;
    const segment = getSegmentForSentence(nextSentenceId);
    if (!segment) return null;

    // Check if this segment ID was changed (map is oldId -> newId, so find where newId matches)
    const oldId = Array.from(segmentIdChanges.entries()).find(([_, newId]) => newId === segment.id)?.[0];

    if (oldId && oldId !== segment.id) {
      return { label: `¶ ${segment.id}`, oldId };
    }
    return { label: `¶ ${segment.id}` };
  };

  // Handle boundary toggle
  const handleToggleBoundary = (sentenceIndex: number) => {
    if (!sentences || !segments || !onBoundaryToggle) return;

    // sentenceIndex is the index where we want to add/remove a boundary
    // Check if there's already a boundary at this index
    const hasBoundary = segmentBoundaries.has(sentenceIndex);
    onBoundaryToggle(sentenceIndex, hasBoundary);
    setLastChangedBoundary(sentenceIndex - 1); // Visual feedback at the boundary area
    // Clear after animation
    setTimeout(() => setLastChangedBoundary(null), 1000);
  };

  // Handle save
  const handleSave = async () => {
    if (!onSave) return;

    setIsSaving(true);
    setSaveMessage(null);

    try {
      const result = await onSave();
      if (result.success) {
        setSaveMessage('Saved successfully');
        setTimeout(() => setSaveMessage(null), 2000);
      } else {
        setSaveMessage(result.error || 'Failed to save');
        setTimeout(() => setSaveMessage(null), 3000);
      }
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : 'Failed to save');
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  if (!sentences || !segments) {
    return <div className="flex h-full items-center justify-center text-gray-500">Load a chapter to view text</div>;
  }

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto bg-white dark:bg-black flex flex-col"
      onMouseLeave={() => setCurrentSegmentId(null)}
    >
      {/* Undo/Redo/Save toolbar */}
      {(canUndo || canRedo || hasUnsavedChanges) && (
        <div className="sticky top-0 z-30 bg-white dark:bg-black border-b border-gray-200 dark:border-gray-800 px-4 py-2 flex items-center gap-2">
          <button
            onClick={onUndo}
            disabled={!canUndo}
            className={`px-3 py-1 text-sm rounded border transition-colors flex items-center gap-1.5 ${
              canUndo
                ? 'border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-900 text-gray-700 dark:text-gray-300'
                : 'border-gray-200 dark:border-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed'
            }`}
          >
            <Icon icon="mdi:undo" className={`w-3.5 h-3.5 ${!canUndo ? 'opacity-40' : ''}`} />
            <span>Undo</span>
          </button>
          <button
            onClick={onRedo}
            disabled={!canRedo}
            className={`px-3 py-1 text-sm rounded border transition-colors flex items-center gap-1.5 ${
              canRedo
                ? 'border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-900 text-gray-700 dark:text-gray-300'
                : 'border-gray-200 dark:border-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed'
            }`}
          >
            <Icon icon="mdi:redo" className={`w-3.5 h-3.5 ${!canRedo ? 'opacity-40' : ''}`} />
            <span>Redo</span>
          </button>
          <div className="flex-1" />
          {saveMessage && (
            <span
              className={`text-xs px-2 py-1 rounded ${
                saveMessage.includes('success')
                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200'
                  : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200'
              }`}
            >
              {saveMessage}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={!hasUnsavedChanges || isSaving}
            className={`px-4 py-1 text-sm rounded border font-medium transition-colors flex items-center gap-1.5 ${
              hasUnsavedChanges && !isSaving
                ? 'border-blue-500 bg-blue-500 text-white hover:bg-blue-600 dark:bg-blue-600 dark:border-blue-600 dark:hover:bg-blue-700'
                : 'border-gray-200 dark:border-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed bg-gray-50 dark:bg-gray-900'
            }`}
          >
            <Icon
              icon="material-symbols:save-rounded"
              className={`w-3.5 h-3.5 ${!hasUnsavedChanges || isSaving ? 'opacity-40' : ''}`}
            />
            <span>{isSaving ? 'Saving...' : 'Save'}</span>
          </button>
        </div>
      )}
      <div className="max-w-3xl mx-auto py-8 px-6 space-y-0 flex-1">
        {sentences.sentences.map((sentence, index) => {
          const segment = getSegmentForSentence(sentence.id);
          const isSegmentStart = segmentBoundaries.has(index);
          const hasBoundaryAfter = hasSegmentBoundary(index);
          const boundaryLabelData = hasBoundaryAfter ? getBoundaryLabel(index) : null;
          const boundaryLabel = boundaryLabelData?.label || null;
          const boundaryOldId = boundaryLabelData?.oldId;
          const isCurrentSegment = segment?.id === currentSegmentId || segment?.id === selectedSegmentId;
          const showHoverBoundary = hoveredBoundary === index;
          const isModified = segment?.id && modifiedSegmentIds.has(segment.id);

          // Get label for first segment if this is the very first sentence
          const firstSegmentOldId =
            segment?.id && Array.from(segmentIdChanges.entries()).find(([_, newId]) => newId === segment.id)?.[0];
          const firstSegmentLabel = index === 0 && segment ? `¶ ${segment.id}` : null;

          // Check for block boundary
          const isBlockStart = blockBoundaries.has(index);
          const hasBlockChangeAfter =
            index < sentences.sentences.length - 1 && sentence.blockId !== sentences.sentences[index + 1]?.blockId;
          const currentBlockId = sentence.blockId;

          return (
            <div
              key={sentence.id}
              ref={(el) => {
                if (el) {
                  sentenceRefs.current.set(sentence.id, el);
                } else {
                  sentenceRefs.current.delete(sentence.id);
                }
              }}
              className="relative"
            >
              {/* Boundary before first segment */}
              {firstSegmentLabel && (
                <div className="relative h-4 mb-1">
                  <div
                    className={`absolute inset-x-0 top-1 border-t-2 ${
                      isModified ? 'border-orange-500 dark:border-orange-400' : 'border-gray-600 dark:border-gray-400'
                    }`}
                  >
                    <span className="absolute left-0 -top-2 text-xs font-medium bg-white dark:bg-black px-1">
                      {firstSegmentOldId && firstSegmentOldId !== segment?.id ? (
                        <>
                          <span className="text-gray-600 dark:text-gray-400">¶ {firstSegmentOldId}</span>
                          <span className="mx-1 text-gray-600 dark:text-gray-400">→</span>
                          <span className="text-orange-600 dark:text-orange-400 font-semibold">{segment?.id}</span>
                        </>
                      ) : (
                        <>
                          <span
                            className={
                              isModified
                                ? 'text-orange-600 dark:text-orange-400 font-semibold'
                                : 'text-gray-600 dark:text-gray-400'
                            }
                          >
                            {firstSegmentLabel}
                          </span>
                          {isModified && !firstSegmentOldId && (
                            <span className="ml-1 text-orange-600 dark:text-orange-400">*</span>
                          )}
                        </>
                      )}
                    </span>
                  </div>
                </div>
              )}

              {/* Block boundary indicator (reference) */}
              {isBlockStart && currentBlockId && (
                <div className="relative h-2 mb-0.5">
                  <div className="absolute inset-x-0 top-0.5 border-t border-dashed border-gray-300 dark:border-gray-700 opacity-40">
                    <span className="absolute right-0 -top-1.5 text-[10px] font-mono text-gray-400 dark:text-gray-600 bg-white dark:bg-black px-1">
                      {currentBlockId}
                    </span>
                  </div>
                </div>
              )}

              {/* Sentence content */}
              <div
                className={`group relative py-2 px-3 transition-colors ${
                  sentence.isCode
                    ? 'bg-gray-50 dark:bg-gray-900 font-mono text-sm border-l-2 border-gray-300 dark:border-gray-700'
                    : ''
                } ${
                  isCurrentSegment
                    ? 'bg-blue-50 dark:bg-blue-950/30'
                    : sentence.isCode
                      ? ''
                      : 'hover:bg-gray-50/50 dark:hover:bg-gray-900/30'
                } ${segment?.id ? 'cursor-pointer' : ''}`}
                onClick={() => {
                  if (segment?.id && onSegmentClick) {
                    onSegmentClick(segment.id);
                  }
                }}
                onMouseEnter={() => {
                  if (segment?.id) setCurrentSegmentId(segment.id);
                }}
                onMouseLeave={() => {
                  // Don't clear currentSegmentId immediately to keep highlight visible
                }}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`text-xs font-mono text-gray-400 dark:text-gray-500 shrink-0 ${
                      sentence.isCode ? 'mt-0.5' : ''
                    }`}
                  >
                    {sentence.id}
                  </span>
                  <span
                    className={`flex-1 ${
                      sentence.isCode
                        ? 'text-gray-800 dark:text-gray-200 whitespace-pre'
                        : 'text-lg text-gray-900 dark:text-gray-100'
                    }`}
                  >
                    {sentence.source}
                  </span>
                </div>
              </div>

              {/* Boundary area */}
              {index < sentences.sentences.length - 1 && (
                <div
                  className="relative h-4 -mt-1 cursor-pointer z-10"
                  onMouseEnter={() => setHoveredBoundary(index)}
                  onMouseLeave={() => setHoveredBoundary(null)}
                >
                  {/* Boundary line */}
                  {hasBoundaryAfter ? (
                    <div
                      className={`absolute inset-x-0 top-1 border-t-2 transition-all ${
                        lastChangedBoundary === index
                          ? 'border-green-500 dark:border-green-400 animate-pulse'
                          : isModified
                            ? 'border-orange-500 dark:border-orange-400'
                            : 'border-gray-600 dark:border-gray-400'
                      }`}
                    >
                      <span className="absolute left-0 -top-2 text-xs font-medium bg-white dark:bg-black px-1">
                        {boundaryOldId && boundaryLabel ? (
                          <>
                            <span className="text-gray-600 dark:text-gray-400">¶ {boundaryOldId}</span>
                            <span className="mx-1 text-gray-600 dark:text-gray-400">→</span>
                            <span className="text-orange-600 dark:text-orange-400 font-semibold">{boundaryLabel}</span>
                          </>
                        ) : (
                          <>
                            <span
                              className={
                                isModified
                                  ? 'text-orange-600 dark:text-orange-400 font-semibold'
                                  : 'text-gray-600 dark:text-gray-400'
                              }
                            >
                              {boundaryLabel}
                            </span>
                            {isModified && !boundaryOldId && (
                              <span className="ml-1 text-orange-600 dark:text-orange-400">*</span>
                            )}
                          </>
                        )}
                      </span>
                    </div>
                  ) : (
                    <>
                      {/* Faint dotted line - only visible on hover or after change */}
                      {(showHoverBoundary || lastChangedBoundary === index) && (
                        <div
                          className={`absolute inset-x-0 top-1.5 border-t border-dotted transition-all ${
                            lastChangedBoundary === index
                              ? 'opacity-100 border-green-500 dark:border-green-400 border-solid border-t-2'
                              : 'opacity-50 border-gray-300 dark:border-gray-600'
                          }`}
                        />
                      )}
                      {/* Block boundary indicator (reference) - between sentences */}
                      {hasBlockChangeAfter && index < sentences.sentences.length - 1 && (
                        <div className="absolute inset-x-0 top-0.5 border-t border-dashed border-gray-300 dark:border-gray-700 opacity-30 pointer-events-none">
                          <span className="absolute right-0 -top-1.5 text-[10px] font-mono text-gray-400 dark:text-gray-600 bg-white dark:bg-black px-1">
                            {sentences.sentences[index + 1]?.blockId || ''}
                          </span>
                        </div>
                      )}
                    </>
                  )}

                  {/* Toggle button on hover */}
                  {showHoverBoundary && (
                    <div className="absolute left-1/2 -translate-x-1/2 -top-1 z-20">
                      <button
                        onClick={() => handleToggleBoundary(index + 1)}
                        className="px-3 py-1 text-xs bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded shadow-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center gap-1.5"
                      >
                        {hasBoundaryAfter ? (
                          <>
                            <Icon icon="material-symbols:cell-merge-rounded" className="w-3 h-3" />
                            <span>Merge</span>
                          </>
                        ) : (
                          <>
                            <Icon icon="mdi:scissors-cutting" className="w-3 h-3" />
                            <span>Split here</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
