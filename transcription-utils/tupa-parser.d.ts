declare module 'tupa-parser' {
  import type { 音韻地位 } from 'tshet-uinh';
  export default function convertTUPATo音韻地位(tupa: string): 音韻地位;
}
