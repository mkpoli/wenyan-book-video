import TshetUinh, { 音韻地位 } from 'tshet-uinh';

interface Pronunciation {
  pronunciation: 音韻地位;
  definition: string;
}

export function getDefinitionFromSinograph(word: string): Pronunciation[] {
  return TshetUinh.資料.query字頭(word).map((result) => {
    result.釋義;
    return {
      pronunciation: result.音韻地位,
      definition: result.釋義,
    };
  });
}
