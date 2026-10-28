> Historical document from the supplied archive. For the repaired 2D implementation and current checks, see README.md and docs/VALIDATION-UPDATED.md.

# BLU: active 3D companion

The active character is `src/blu-3d.js`, with Three.js loaded from the installed local package. The canvas persists outside the application DOM so UI rendering does not reconstruct the rig. Meshes include the glossy blue body, face, jointed arms, seated legs, biryani bowl with instanced rice, garnish, chicken and spoon.

The latest motion revision uses delta-time exponential damping for screen position, limbs, body rotation and facial transitions. The WebGL backing buffer remains fixed during travel instead of being resized every frame. The bowl follows a smooth side arc from the head to the lap. The left hand supports the bowl; the right follows a 5.4-second scoop, lift, bite and return cycle. Position is continuous across cycle boundaries. A short settling period precedes eating. At completion, the bowl returns to the head and BLU moves back to the right-side slot. On narrow screens, the designated slot is above the conversation.

During generation the actor ignores pointer input and the workspace is inert, as requested. Generation is driven by actual backend status. Error completion also releases the interface and returns BLU to the dock. Voice amplitude animates the mouth during greetings and quiz feedback. No random emotion timers are used to interrupt speech.

`src/motion-math.mjs` isolates the trajectory calculations for continuity tests. Reduced-motion preferences limit ambient movement; the interaction remains available without relying on motion to convey progress. The reference board remains user-supplied artwork. `blu-companion/` is a previous standalone SVG module and is not the active character.
