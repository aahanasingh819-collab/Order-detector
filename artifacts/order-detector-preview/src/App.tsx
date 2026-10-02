function App() {
  return (
    <main className="preview-shell" aria-label="Order Detector live preview">
      <iframe
        className="preview-frame"
        src="/"
        title="Order Detector fraud-review workspace"
        aria-label="Live Order Detector website"
        tabIndex={0}
      />
    </main>
  );
}

export default App;
