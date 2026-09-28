--  Representation-independent client proof.
--
--  This unit may only use the visible abstraction of Ring_Buffer: the ghost
--  Model, the Sequences instantiation and the public operations. It must not
--  depend on Content, First, Length, physical indices or private helpers.
--  It is intended to be reused unchanged by the representation-refactor
--  benchmark (A3).

with Ring_Buffer; use Ring_Buffer;

package Ring_Buffer_Client_Proof with SPARK_Mode is

   use type Ring_Buffer.Sequences.Sequence;

   procedure Push_Push_Pop (A, B : Element; X : out Element)
   with Pre    => A /= B,
        Global => null;
   --  Initialize Q; Push (Q, A); Push (Q, B); Pop (Q, X);
   --  proves X = A and Model (Q) = [B] in the body.

   procedure Rotate (Q : in out Buffer)
   with Pre    => not Is_Empty (Q),
        Post   => Model (Q)
                  = Sequences.Add (Sequences.Remove (Model (Q)'Old, 1),
                                   Sequences.Get (Model (Q)'Old, 1)),
        Global => null;
   --  Moves the head element of an arbitrary non-empty queue to its tail
   --  using Peek, Pop and Push. Requires the public capacity bound on Model
   --  to show that Push's precondition holds after Pop.

end Ring_Buffer_Client_Proof;
