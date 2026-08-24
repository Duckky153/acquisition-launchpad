import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DemoMission, GuidedDemo } from "./DemoGuide";

describe("DemoMission", () => {
  it("explains the problem, user, outcome, and one-decision-left state", async () => {
    const user = userEvent.setup();
    const onReviewDecision = vi.fn();
    const onStartTour = vi.fn();
    render(<DemoMission approvedCount={17} isReady={false} onReviewDecision={onReviewDecision} onStartTour={onStartTour} totalCount={18} />);

    expect(screen.getByText("Problem")).toBeInTheDocument();
    expect(screen.getByText("User")).toBeInTheDocument();
    expect(screen.getByText("Outcome")).toBeInTheDocument();
    expect(screen.getByText("17/18")).toBeInTheDocument();
    expect(screen.getByText(/HZ-115/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Review final decision/ }));
    expect(onReviewDecision).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: /Start full tour/ }));
    expect(onStartTour).toHaveBeenCalledOnce();
  });
});

describe("GuidedDemo", () => {
  function renderGuide() {
    const onClose = vi.fn();
    const onNavigate = vi.fn();
    const onOpenAudit = vi.fn();
    render(
      <GuidedDemo
        approvedCount={17}
        isReady={false}
        onClose={onClose}
        onNavigate={onNavigate}
        onOpenAudit={onOpenAudit}
        open
        openBlockerCount={1}
        startAt="overview"
        totalCount={18}
      />,
    );
    return { onClose, onNavigate, onOpenAudit };
  }

  it("navigates every evidence surface and opens the audit ledger", async () => {
    const user = userEvent.setup();
    const { onNavigate, onOpenAudit } = renderGuide();
    await waitFor(() => expect(screen.getByRole("heading", { name: /Acquired companies rarely/ })).toHaveFocus());
    expect(onNavigate).toHaveBeenLastCalledWith("overview", expect.any(Number));

    for (const anchor of ["entities", "mapping", "blockers", "sequence", "audit"]) {
      await user.click(screen.getByRole("button", { name: /Next/ }));
      expect(onNavigate).toHaveBeenLastCalledWith(anchor, expect.any(Number));
    }
    await user.click(screen.getByRole("button", { name: "Open audit ledger" }));
    expect(onOpenAudit).toHaveBeenCalledOnce();
  });

  it("supports keyboard navigation, restart, and Escape dismissal", async () => {
    const user = userEvent.setup();
    const { onClose, onNavigate } = renderGuide();
    const guide = screen.getByRole("complementary", { name: "Three-minute guided demo" });

    guide.focus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(onNavigate).toHaveBeenLastCalledWith("mapping", expect.any(Number));
    await user.click(screen.getByRole("button", { name: "Restart guide" }));
    expect(onNavigate).toHaveBeenLastCalledWith("overview", expect.any(Number));
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("opens directly on the final mapping decision when requested", async () => {
    const onNavigate = vi.fn();
    render(
      <GuidedDemo
        approvedCount={17}
        isReady={false}
        onClose={() => undefined}
        onNavigate={onNavigate}
        onOpenAudit={() => undefined}
        open
        openBlockerCount={1}
        startAt="mapping"
        totalCount={18}
      />,
    );

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Review the one decision left/ })).toHaveFocus(),
    );
    expect(onNavigate).toHaveBeenLastCalledWith("mapping", expect.any(Number));
  });

  it("returns keyboard focus to the control that opened the guide", async () => {
    const user = userEvent.setup();
    function GuideHarness(): React.ReactElement {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)} type="button">Open guide</button>
          <GuidedDemo
            approvedCount={17}
            isReady={false}
            onClose={() => setOpen(false)}
            onNavigate={() => undefined}
            onOpenAudit={() => undefined}
            open={open}
            openBlockerCount={1}
            startAt="overview"
            totalCount={18}
          />
        </>
      );
    }

    render(<GuideHarness />);
    const opener = screen.getByRole("button", { name: "Open guide" });
    await user.click(opener);
    await waitFor(() => expect(screen.getByRole("heading", { name: /Acquired companies rarely/ })).toHaveFocus());
    await user.keyboard("{Escape}");
    await waitFor(() => expect(opener).toHaveFocus());
  });
});
