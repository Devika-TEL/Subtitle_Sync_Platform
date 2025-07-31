import React from "react";
import {
  render,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import App from "./App";

// Mock the fetch API used by App.js for backend requests
global.fetch = jest.fn();

function mockCorrectionFlow() {
  // Simulate upload response (correction), then job polling, then subtitle fetch
  // 1: Correction POST returns job start
  fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job_id: 11,
        status: "in_progress",
        message: "Files uploaded. Correction started.",
        output_subtitle_id: null,
      }),
    })
    // 2: GET /api/jobs/{id} - "in_progress"
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 11,
        status: "in_progress",
        message: "Correction underway.",
        progress: 33,
        output_subtitle_id: null,
      }),
    })
    // 3: GET /api/jobs/{id} - "success"
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 11,
        status: "success",
        message: "Correction complete.",
        progress: 100,
        output_subtitle_id: 64,
      }),
    })
    // 4: GET /api/subtitles/64 - subtitle exists
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 64,
        video_id: 1,
        filename: "corrected_sample.srt",
        format: "srt",
        file_path: "some_path/corrected_sample.srt",
        is_original: false,
        created_at: "2024-08-01T12:00:00Z",
      }),
    });
}

function mockGenerationFlow() {
  // Simulate POST/generation and job polling
  fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        job_id: 21,
        status: "in_progress",
        message: "Generation underway.",
        output_subtitle_id: null,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 21,
        status: "in_progress",
        message: "Still processing.",
        progress: 50,
        output_subtitle_id: null,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 21,
        status: "success",
        message: "Generation complete.",
        progress: 100,
        output_subtitle_id: 77,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 77,
        video_id: 3,
        filename: "generated_en.srt",
        format: "srt",
        file_path: "some_path/generated_en.srt",
        is_original: false,
        created_at: "2024-08-01T13:00:00Z",
        notes: "Auto-generated",
      }),
    });
}

afterEach(() => {
  jest.clearAllMocks();
});

describe("E2E Workflow UI/UX Tests", () => {
  test("Subtitle Correction: end-to-end happy path", async () => {
    mockCorrectionFlow();
    render(<App />);
    // Should default to correction tab
    expect(screen.getByRole("heading", { name: /subtitle correction/i })).toBeInTheDocument();

    // Attach dummy files to both file pickers
    const file1 = new File(["dummymp4"], "video.mp4", { type: "video/mp4" });
    const file2 = new File(["dummy srt"], "sample.srt", { type: "text/plain" });

    const videoBtn = screen.getByRole("button", { name: /video file/i });
    fireEvent.click(videoBtn);
    const inputVideo = screen.getByLabelText(/video file/i, { selector: "input" });
    // Setting file via input fires change event
    fireEvent.change(inputVideo, { target: { files: [file1] } });

    // Subtitle file
    const subBtn = screen.getByRole("button", { name: /subtitle file/i });
    fireEvent.click(subBtn);
    const inputSub = screen.getByLabelText(/subtitle file/i, { selector: "input" });
    fireEvent.change(inputSub, { target: { files: [file2] } });

    // Submit
    const submit = screen.getByRole("button", { name: /submit.*correction/i });
    expect(submit).not.toBeDisabled();
    fireEvent.click(submit);

    // Uploading spinner shows up
    expect(await screen.findByText(/uploading\.\.\. please wait/i)).toBeInTheDocument();

    // Mock fetch resolves in background: job status should now become "in_progress"
    await waitFor(() => expect(screen.getByText(/job status:/i)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText(/in_progress/i)).toBeInTheDocument();
    expect(screen.getByText(/correction underway/i)).toBeInTheDocument();

    // Job progresses to "success" (polling completes)
    await waitFor(() => expect(screen.getByText(/success/i)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText(/correction complete/i)).toBeInTheDocument();
    // Subtitle output ready panel appears
    expect(screen.getByText(/subtitle output is ready/i)).toBeInTheDocument();
  });

  test("Subtitle Generation: end-to-end happy path", async () => {
    mockGenerationFlow();
    render(<App />);
    // Switch to generation tab:
    const genTab = screen.getByRole("tab", { selected: false, name: /generation/i }) || screen.getByRole("button", { name: /subtitle generation/i });
    fireEvent.click(genTab);

    expect(screen.getByRole("heading", { name: /subtitle generation/i })).toBeInTheDocument();

    const file3 = new File(["dummymp4"], "video2.mp4", { type: "video/mp4" });
    const videoBtn = screen.getByRole("button", { name: /video file/i });
    fireEvent.click(videoBtn);
    const inputVideo = screen.getByLabelText(/video file/i, { selector: "input" });
    fireEvent.change(inputVideo, { target: { files: [file3] } });

    // Select a language in the dropdown
    const langSelect = screen.getByLabelText(/target language/i);
    fireEvent.change(langSelect, { target: { value: "en" } });

    // Submit
    const submit = screen.getByRole("button", { name: /generate.*subtitles/i });
    fireEvent.click(submit);

    // Upload spinner
    expect(await screen.findByText(/uploading\.\.\. please wait/i)).toBeInTheDocument();

    // Wait for job status - in_progress
    await waitFor(() => screen.getByText(/job status:/i), { timeout: 3000 });
    expect(screen.getByText(/in_progress/i)).toBeInTheDocument();
    expect(screen.getByText(/still processing/i)).toBeInTheDocument();

    // Wait for job status to succeed
    await waitFor(() => screen.getByText(/success/i), { timeout: 3000 });
    expect(screen.getByText(/generation complete/i)).toBeInTheDocument();
    expect(screen.getByText(/subtitle output is ready/i)).toBeInTheDocument();
  });

  test("Error handling: missing file selection", async () => {
    render(<App />);
    // Correction should be default
    // Just submit with nothing selected:
    fireEvent.click(screen.getByRole("button", { name: /submit.*correction/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/please select both/i);

    // Switch to generation
    const genTab = screen.getByRole("tab", { selected: false, name: /generation/i }) || screen.getByRole("button", { name: /subtitle generation/i });
    fireEvent.click(genTab);
    fireEvent.click(screen.getByRole("button", { name: /generate.*subtitles/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/please select a video.*language/i);
  });

  test("Displays network/server error in submission", async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Test upload error" }),
    });

    render(<App />);
    // Correction tab: pick files, submit, see error panel
    const file1 = new File(["dummymp4"], "video.mp4", { type: "video/mp4" });
    const file2 = new File(["dummy srt"], "sample.srt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/video file/i, { selector: "input" }), {
      target: { files: [file1] },
    });
    fireEvent.change(screen.getByLabelText(/subtitle file/i, { selector: "input" }), {
      target: { files: [file2] },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit.*correction/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/test upload error/i);
  });

  test("Displays polling/job status fetch error", async () => {
    // Correction flow: POST is fine, but status polling fails
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: 12,
          status: "in_progress",
          message: "Correction started.",
          output_subtitle_id: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Job status fetch failed" }),
      });

    render(<App />);
    const file1 = new File(["dummymp4"], "video.mp4", { type: "video/mp4" });
    const file2 = new File(["dummy srt"], "sample.srt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/video file/i, { selector: "input" }), {
      target: { files: [file1] },
    });
    fireEvent.change(screen.getByLabelText(/subtitle file/i, { selector: "input" }), {
      target: { files: [file2] },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit.*correction/i }));

    // Wait for polling error
    expect(await screen.findByRole("alert")).toHaveTextContent(/error updating job status/i);
  });
});
