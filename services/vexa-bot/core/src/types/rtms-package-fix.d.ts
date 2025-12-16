// Type fix for @zoom/rtms package type definition error
// The package's rtms.d.ts file references DeskshareDataCallback which doesn't exist
// This declaration file patches the missing type

declare type DeskshareDataCallback = any;

// Extend the RTMS module to include missing types
declare module '@zoom/rtms' {
  export type DeskshareDataCallback = any;
}





