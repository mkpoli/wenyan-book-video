/// <reference path="./tupa-parser.d.ts" />
import type { 音韻地位 } from 'tshet-uinh';
import { convertIPAToTranscription } from './cinix';
import convertTUPATo音韻地位 from 'tupa-parser';

export function convertCinixTo音韻地位(cinix: string): 音韻地位 {
  return convertTUPATo音韻地位(convertIPAToTranscription(cinix));
}
export { convertIPAToTranscription as convertCinixToTUPA };
export { getDefinitionFromSinograph } from './definition';
