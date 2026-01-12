// Daum Postcode API type declarations
declare global {
  interface Window {
    daum: {
      Postcode: new (options: {
        oncomplete: (data: {
          roadAddress: string;
          jibunAddress: string;
          userSelectedType: "R" | "J";
          bname?: string;
          buildingName?: string;
          apartment?: string;
        }) => void;
        width?: number;
        height?: number;
      }) => {
        open: () => void;
      };
      postcode: {
        load: (callback: () => void) => void;
      };
    };
  }
}

export {};
