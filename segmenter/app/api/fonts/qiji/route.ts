import { NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

const QIJI_FONT_PATH = join(
  process.cwd(),
  '..',
  'renderer',
  'public',
  'fonts',
  'qiji-combo.ttf',
);

export async function GET() {
  try {
    const fontBuffer = await readFile(QIJI_FONT_PATH);

    return new NextResponse(fontBuffer, {
      headers: {
        'Content-Type': 'font/ttf',
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch (error) {
    console.error('Failed to load Qiji font:', error);
    return NextResponse.json(
      { error: 'Failed to load font' },
      { status: 500 },
    );
  }
}

