import { useRef, useState } from "react";

// The id comes from your form's share link: docs.google.com/forms/d/e/<id>/viewform
const FORM_ID = "1FAIpQLScU2ZbhWCi0iWpxQf8SrkZn0OopxQ14FeHZs0MaDCwGQ1qmrg";
const FORM_URL = `https://docs.google.com/forms/d/e/${FORM_ID}/viewform`;

export default function Survey() {
  const dialog = useRef(null);
  const [opened, setOpened] = useState(false); // the form only loads once someone asks for it

  const open = () => {
    setOpened(true);
    dialog.current.showModal();
  };
  const close = () => dialog.current.close();

  return (
    <div className="card survey-note">
      <div>
        <h2>Help improve this app</h2>
        <p className="muted">
          Your feedback helps the lab make the crowding information more accurate and more useful.
          The survey is short and takes about a minute.
        </p>
      </div>
      <button className="btn primary" onClick={open}>
        Give feedback
      </button>

      <dialog
        ref={dialog}
        className="survey"
        aria-labelledby="survey-title"
        onClick={(e) => e.target === dialog.current && close()} // a click on the dimmed backdrop closes it
      >
        <div className="survey-head">
          <div>
            <h2 id="survey-title">Cafeteria crowding survey</h2>
            <p className="muted" style={{ margin: "2px 0 0" }}>
              Thank you for helping the lab improve this app.
            </p>
          </div>
          <button className="btn" onClick={close} aria-label="Close survey">
            Close
          </button>
        </div>
        {opened && (
          <iframe
            className="survey-frame"
            title="Katsura Main Student Cafeteria crowding survey"
            src={`${FORM_URL}?embedded=true`}
          />
        )}
        <p className="muted survey-foot">
          Form not loading?{" "}
          <a href={FORM_URL} target="_blank" rel="noreferrer">
            Open the survey in a new tab
          </a>
          .
        </p>
      </dialog>
    </div>
  );
}