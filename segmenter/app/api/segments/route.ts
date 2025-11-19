import { NextResponse } from 'next/server';
import { readdir } from 'fs/promises';
import { join } from 'path';

// Resolve path relative to the segmenter directory (process.cwd() in Next.js API routes)
// segmenter -> repo root -> renderer/public/segments
const SEGMENTS_DIR = join(process.cwd(), '..', 'renderer', 'public', 'segments');

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

/**
 * GET /api/segments
 * List all available chapter segment files
 */
export async function GET() {
  try {
    const files = await readdir(SEGMENTS_DIR);
    const segmentFiles = files
      .filter((file) => file.endsWith('.segments.json'))
      .sort((a, b) => {
        const numA = parseInt(a.match(/c(\d+)/)?.[1] || '0', 10);
        const numB = parseInt(b.match(/c(\d+)/)?.[1] || '0', 10);
        return numA - numB;
      })
      .map((file) => file.replace('.segments.json', ''));

    return NextResponse.json({ chapters: segmentFiles });
  } catch (error) {
    console.error('Error reading segments directory:', error);
    return NextResponse.json(
      { error: 'Failed to list segments' },
      { status: 500 }
    );
  }
}

