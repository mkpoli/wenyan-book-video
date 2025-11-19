import { NextRequest, NextResponse } from 'next/server';
import { readFile, writeFile } from 'fs/promises';
import { join } from 'path';
import type { ChapterSegments } from '../route';

// Resolve path relative to the segmenter directory (process.cwd() in Next.js API routes)
// segmenter -> repo root -> renderer/public/segments
const SEGMENTS_DIR = join(process.cwd(), '..', 'renderer', 'public', 'segments');

/**
 * GET /api/segments/[chapterId]
 * Load a specific chapter's segments file
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ chapterId: string }> }
) {
  try {
    const { chapterId } = await params;
    
    // Sanitize chapterId to prevent path traversal
    if (!/^c\d+$/.test(chapterId)) {
      return NextResponse.json(
        { error: 'Invalid chapter ID format' },
        { status: 400 }
      );
    }

    const filePath = join(SEGMENTS_DIR, `${chapterId}.segments.json`);
    
    try {
      const fileContents = await readFile(filePath, 'utf-8');
      const data: ChapterSegments = JSON.parse(fileContents);
      
      return NextResponse.json(data);
    } catch (fileError) {
      if ((fileError as NodeJS.ErrnoException).code === 'ENOENT') {
        return NextResponse.json(
          { error: `Chapter ${chapterId} not found` },
          { status: 404 }
        );
      }
      throw fileError;
    }
  } catch (error) {
    console.error('Error loading segments:', error);
    return NextResponse.json(
      { error: 'Failed to load segments' },
      { status: 500 }
    );
  }
}

/**
 * PUT /api/segments/[chapterId]
 * Save a specific chapter's segments file
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ chapterId: string }> }
) {
  try {
    const { chapterId } = await params;
    
    // Sanitize chapterId to prevent path traversal
    if (!/^c\d+$/.test(chapterId)) {
      return NextResponse.json(
        { error: 'Invalid chapter ID format' },
        { status: 400 }
      );
    }

    const body = await request.json();
    const segments: ChapterSegments = body;

    // Validate the structure
    if (!segments.chapterId || !segments.chapterNumber || !Array.isArray(segments.segments)) {
      return NextResponse.json(
        { error: 'Invalid segments structure' },
        { status: 400 }
      );
    }

    // Ensure chapterId matches
    if (segments.chapterId !== chapterId) {
      return NextResponse.json(
        { error: 'Chapter ID mismatch' },
        { status: 400 }
      );
    }

    const filePath = join(SEGMENTS_DIR, `${chapterId}.segments.json`);
    
    // Write the file with proper formatting (2-space indent, UTF-8)
    const fileContents = JSON.stringify(segments, null, 2);
    await writeFile(filePath, fileContents, 'utf-8');
    
    return NextResponse.json({ success: true, message: 'Segments saved successfully' });
  } catch (error) {
    console.error('Error saving segments:', error);
    return NextResponse.json(
      { error: 'Failed to save segments' },
      { status: 500 }
    );
  }
}
