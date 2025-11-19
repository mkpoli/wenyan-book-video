import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

const TRANSLATIONS_DIR = join(process.cwd(), '..', 'renderer', 'public', 'translations');

export interface TranslationEntry {
  source: string;
  translation: string;
}

export interface ChapterTranslations {
  [sentenceId: string]: TranslationEntry;
}

/**
 * GET /api/translations/[chapterId]
 * Load a specific chapter's translations file
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

    const filePath = join(TRANSLATIONS_DIR, `${chapterId}.translations.json`);

    try {
      const fileContents = await readFile(filePath, 'utf-8');
      const data: ChapterTranslations = JSON.parse(fileContents);
      return NextResponse.json(data);
    } catch (fileError) {
      if ((fileError as NodeJS.ErrnoException).code === 'ENOENT') {
        return NextResponse.json(
          { error: `Translations for ${chapterId} not found` },
          { status: 404 }
        );
      }
      throw fileError;
    }
  } catch (error) {
    console.error('Error loading translations:', error);
    return NextResponse.json(
      { error: 'Failed to load translations' },
      { status: 500 }
    );
  }
}

