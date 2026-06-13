import { type FC, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useTranslate } from "@/utils/i18n";
import { useEditorContext } from "../state";

const INPUT_CLASS = "block w-full rounded-md border border-border bg-background px-2 py-1 text-sm data-[invalid=true]:border-destructive";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

// Native datetime-local uses the user's local time and the format
// "YYYY-MM-DDTHH:mm" (no seconds, no timezone). We treat the value as local
// time when converting back to a Date, so the picker round-trips user picks.
function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInputValue(value: string): Date | undefined {
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return undefined;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]), m[6] ? Number(m[6]) : 0);
  return Number.isNaN(d.getTime()) ? undefined : d;
}

const TimestampInput: FC<{
  label: string;
  date: Date | undefined;
  onChange: (date: Date) => void;
}> = ({ label, date, onChange }) => {
  const [invalid, setInvalid] = useState(false);
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <input
        type="datetime-local"
        className={INPUT_CLASS}
        data-invalid={invalid}
        value={date ? toLocalInputValue(date) : ""}
        onChange={(e) => {
          const v = e.target.value;
          if (!v) {
            setInvalid(true);
            return;
          }
          const d = fromLocalInputValue(v);
          if (d) {
            setInvalid(false);
            onChange(d);
          } else {
            setInvalid(true);
          }
        }}
      />
    </div>
  );
};

interface TimestampPopoverProps {
  // Edit-mode memos have an updateTime the user may want to override too.
  // In create mode the timestamp is set once and never modified, so the
  // second input is noise.
  showUpdateTime?: boolean;
}

export const TimestampPopover: FC<TimestampPopoverProps> = ({ showUpdateTime = false }) => {
  const t = useTranslate();
  const { state, actions, dispatch } = useEditorContext();
  const { createTime, updateTime } = state.timestamps;

  // Defensive fallback: the popover is always rendered in create mode now,
  // and useMemoInit seeds createTime to "now", so this should not be hit.
  // It exists so the trigger and inputs never show "Invalid Date" if state
  // was reset mid-render.
  const effectiveCreateTime = createTime ?? new Date();
  const effectiveUpdateTime = showUpdateTime ? (updateTime ?? new Date()) : undefined;

  const handleResetToNow = () => {
    const now = new Date();
    dispatch(
      actions.setTimestamps({
        createTime: now,
        updateTime: showUpdateTime ? now : undefined,
      }),
    );
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="w-auto text-sm text-muted-foreground text-left hover:text-foreground transition-colors cursor-pointer"
        >
          {effectiveCreateTime.toLocaleString()}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-2 pt-1 space-y-1">
        <TimestampInput
          label={t("common.created-at")}
          date={effectiveCreateTime}
          onChange={(d) => dispatch(actions.setTimestamps({ createTime: d }))}
        />
        {showUpdateTime && (
          <TimestampInput
            label={t("common.last-updated-at")}
            date={effectiveUpdateTime}
            onChange={(d) => dispatch(actions.setTimestamps({ updateTime: d }))}
          />
        )}
        <div className="flex justify-end pt-1">
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            onClick={handleResetToNow}
          >
            {t("common.reset-to-now")}
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
};
