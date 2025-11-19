import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

const SENTENCES_DIR = join(process.cwd(), '..', 'renderer', 'public', 'sentences');

export interface Sentence {
  id: string;
  chapterId: string;
  blockId: string;
  index: number;
  source: string;
  isCode: boolean;
}

export interface ChapterSentences {
  chapterId: string;
  number: number;
  title: string;
  sentences: Sentence[];
}

/**
 * GET /api/sentences/[chapterId]
 * Load a specific chapter's sentences file
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ chapterId: string }> }) {
  try {
    const { chapterId } = await params;

    // Sanitize chapterId to prevent path traversal
    if (!/^c\d+$/.test(chapterId)) {
      return NextResponse.json({ error: 'Invalid chapter ID format' }, { status: 400 });
    }

    const filePath = join(SENTENCES_DIR, `${chapterId}.sentences.json`);

    try {
      const fileContents = await readFile(filePath, 'utf-8');
      const data: ChapterSentences = JSON.parse(fileContents);

      return NextResponse.json(data);
    } catch (fileError) {
      if ((fileError as NodeJS.ErrnoException).code === 'ENOENT') {
        return NextResponse.json({ error: `Chapter ${chapterId} not found` }, { status: 404 });
      }
      throw fileError;
    }
  } catch (error) {
    console.error('Error loading sentences:', error);
    return NextResponse.json({ error: 'Failed to load sentences' }, { status: 500 });
  }
}
