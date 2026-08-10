import "@testing-library/jest-dom/vitest";

// jsdom does not implement object URLs, and the upload preview uses them.
// Stubbing here rather than in each test keeps the component honest about what
// it actually does with a File.
if (!URL.createObjectURL) {
  URL.createObjectURL = () => "blob:preview";
  URL.revokeObjectURL = () => undefined;
}
