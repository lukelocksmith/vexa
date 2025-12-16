// Type fix for @zoom/rtms package type definition error
// The package references DeskshareDataCallback which doesn't exist
declare module '@zoom/rtms' {
  // Add missing type if needed
  type DeskshareDataCallback = any;
}

// Global type declaration to fix RTMS package error
declare type DeskshareDataCallback = any;

