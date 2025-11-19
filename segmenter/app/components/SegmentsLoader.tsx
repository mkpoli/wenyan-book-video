'use client';

import { useEffect, useState } from 'react';
import { Icon } from '@iconify/react';
import type { ChapterSentences } from '../api/sentences/[chapterId]/route';

export interface Segment {
  id: string;
  chapterId: string;
  segmentIndex: number;
  sentenceIds: string[];
  isCodeBlock: boolean;
  isListItem?: boolean;
}

export interface ChapterSegments {
  chapterId: string;
  chapterNumber: number;
  segments: Segment[];
}

interface SegmentsLoaderProps {
  chapterId?: string;
  onDataLoad?: (sentences: ChapterSentences | null, segments: ChapterSegments | null) => void;
  onSegmentClick?: (segmentId: string) => void;
  selectedSegmentId?: string | null;
  externalSegments?: ChapterSegments | null;
  segmentIdChanges?: Map<string, string>;
  modifiedSegmentIds?: Set<string>;
}

export default function SegmentsLoader({
  chapterId,
  onDataLoad,
  onSegmentClick,
  selectedSegmentId,
  externalSegments,
  segmentIdChanges = new Map(),
  modifiedSegmentIds = new Set(),
}: SegmentsLoaderProps) {
  const [availableChapters, setAvailableChapters] = useState<string[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<string>(chapterId || '');
  const [segments, setSegments] = useState<ChapterSegments | null>(null);
  const [sentences, setSentences] = useState<ChapterSentences | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use external segments if provided, otherwise use internal state
  const displaySegments = externalSegments || segments;

  // Load available chapters on mount
  useEffect(() => {
    async function loadChapters() {
      try {
        const response = await fetch('/api/segments');
        if (!response.ok) {
          throw new Error('Failed to load chapters');
        }
        const data = await response.json();
        setAvailableChapters(data.chapters);
        if (data.chapters.length > 0 && !selectedChapter) {
          setSelectedChapter(data.chapters[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load chapters');
      }
    }
    loadChapters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load segments and sentences when chapter changes
  useEffect(() => {
    if (!selectedChapter) return;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [segmentsRes, sentencesRes] = await Promise.all([
          fetch(`/api/segments/${selectedChapter}`),
          fetch(`/api/sentences/${selectedChapter}`),
        ]);

        if (!segmentsRes.ok) {
          throw new Error(`Failed to load segments for ${selectedChapter}`);
        }
        if (!sentencesRes.ok) {
          throw new Error(`Failed to load sentences for ${selectedChapter}`);
        }

        const segmentsData: ChapterSegments = await segmentsRes.json();
        const sentencesData: ChapterSentences = await sentencesRes.json();

        setSegments(segmentsData);
        setSentences(sentencesData);

        if (onDataLoad) {
          onDataLoad(sentencesData, segmentsData);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
        setSegments(null);
        setSentences(null);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [selectedChapter, onDataLoad]);

  return (
    <div className="flex flex-col h-full">
      {/* Chapter selector */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800">
        <div className="relative">
          <Icon
            icon="material-symbols:menu-book"
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 dark:text-gray-400 pointer-events-none"
          />
          <select
            value={selectedChapter}
            onChange={(e) => setSelectedChapter(e.target.value)}
            className="w-full rounded border border-gray-300 pl-10 pr-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
            disabled={loading || availableChapters.length === 0}
          >
            {availableChapters.length === 0 ? (
              <option value="">Loading...</option>
            ) : (
              availableChapters.map((chapter) => {
                const chapterNumber = chapter.match(/\d+/)?.[0] || '';
                return (
                  <option key={chapter} value={chapter}>
                    Chapter {chapterNumber} ({chapter})
                  </option>
                );
              })
            )}
          </select>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-4 bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-200 text-sm flex items-center gap-2">
          <Icon icon="material-symbols:error-rounded" className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Segments list */}
      {displaySegments && (
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-2 space-y-1">
            {displaySegments.segments.map((segment) => {
              const isModified = modifiedSegmentIds.has(segment.id);
              const oldId = Array.from(segmentIdChanges.entries()).find(([_, newId]) => newId === segment.id)?.[0];

              return (
                <div
                  key={segment.id}
                  onClick={() => onSegmentClick?.(segment.id)}
                  className={`rounded px-3 py-2 cursor-pointer transition-colors border ${
                    selectedSegmentId === segment.id
                      ? 'bg-blue-100 dark:bg-blue-950/50 text-blue-900 dark:text-blue-100 border-blue-300 dark:border-blue-700'
                      : isModified
                        ? 'bg-orange-50 dark:bg-orange-950/20 border-orange-300 dark:border-orange-700 hover:bg-orange-100 dark:hover:bg-orange-950/30 text-gray-700 dark:text-gray-300'
                        : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-700 dark:text-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {oldId && oldId !== segment.id ? (
                      <>
                        <span className="text-gray-600 dark:text-gray-400">¶</span>
                        <span className="font-mono text-sm font-medium text-gray-700 dark:text-gray-300">{oldId}</span>
                        <span className="text-xs text-gray-600 dark:text-gray-400">→</span>
                        <span className="font-mono text-sm font-semibold text-orange-600 dark:text-orange-400">
                          {segment.id}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-gray-600 dark:text-gray-400">¶</span>
                        <span className="font-mono text-sm font-medium">
                          {segment.id}
                          {isModified && !oldId && <span className="ml-1 text-orange-600 dark:text-orange-400">*</span>}
                        </span>
                      </>
                    )}
                    {segment.isCodeBlock && (
                      <>
                        <Icon icon="material-symbols:code-rounded" className="w-3.5 h-3.5 opacity-60" />
                        <span className="text-xs opacity-50">Code</span>
                      </>
                    )}
                    {segment.isListItem && (
                      <Icon icon="material-symbols:format-list-bulleted-rounded" className="w-3.5 h-3.5 opacity-60" />
                    )}
                    <div className="ml-auto grid grid-cols-2 items-center gap-1">
                      <Icon icon="material-symbols:article-rounded" className="w-3 h-3 opacity-40" />
                      <span className="text-xs opacity-50  text-right w-full">{segment.sentenceIds.length}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!displaySegments && !error && !loading && (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-sm gap-2">
          <Icon icon="material-symbols:book-outline" className="w-8 h-8 opacity-40" />
          <span>Select a chapter</span>
        </div>
      )}
    </div>
  );
}
