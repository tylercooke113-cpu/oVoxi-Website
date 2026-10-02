import React from 'react';

// Renders the server's plain-text agreement blocks as React elements.
// Never uses dangerouslySetInnerHTML: block text can contain artist-entered values.
export default function AgreementDoc({ blocks }) {
  return (
    <>
      {(blocks || []).map((b, i) => {
        if (b.type === 'signature') {
          return (
            <div
              key={i}
              className="my-3 rounded-lg border border-dashed border-[#bbb] p-2.5 text-center italic text-[#777]"
            >
              Signatures are added here when you sign.
            </div>
          );
        }
        if (b.type === 'title') {
          return <h3 key={i} className="mb-3.5 text-center text-[18px]">{b.text}</h3>;
        }
        if (b.type === 'heading') {
          return <h5 key={i} className="mb-1.5 mt-4 text-[14px] font-bold">{b.text}</h5>;
        }
        if (b.type === 'item') {
          return <p key={i} className="mb-2 pl-[22px]">{b.text}</p>;
        }
        return <p key={i} className="mb-2">{b.text}</p>;
      })}
    </>
  );
}
