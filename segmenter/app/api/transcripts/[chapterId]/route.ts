import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

const TRANSCRIPTS_DIR = join(process.cwd(), '..', 'renderer', 'public', 'transcripts');

export interface TranscriptEntry {
  source: string;
  ipa: string;
  tupa: string;
  choices?: Array<{
    char: string;
    indexInSource: number;
    indexAmongChinese: number;
    sameCharIndex: number;
    ipa: string;
    tupa: string;
  }>;
}

export interface ChapterTranscripts {
  [sentenceId: string]: TranscriptEntry;
}

/**
 * GET /api/transcripts/[chapterId]
 * Load a specific chapter's transcripts file
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ chapterId: string }> }
) {
  try {
    const { chapterId } = await params;

    if (!/^c\d+$/.test(chapterId)) {
      return NextResponse.json(
        { error: 'Invalid chapter ID format' },
        { status: 400 }
      );
    }

    const filePath = join(TRANSCRIPTS_DIR, `${chapterId}.transcripts.json`);

    try {
      const fileContents = await readFile(filePath, 'utf-8');
      const data: ChapterTranscripts = JSON.parse(fileContents);
      return NextResponse.json(data);
    } catch (fileError) {
      if ((fileError as NodeJS.ErrnoException).code === 'ENOENT') {
        return NextResponse.json(
          { error: `Transcripts for ${chapterId} not found` },
          { status: 404 }
        );
      }
      throw fileError;
    }
  } catch (error) {
    console.error('Error loading transcripts:', error);
    return NextResponse.json(
      { error: 'Failed to load transcripts' },
      { status: 500 }
    );
  }
}

