with Ada.Command_Line;
with Ada.Streams;
with Ada.Text_IO;
with CRDT.Security.SHA256;

--  External runtime driver only; not part of the upstream proof project.
--  Arguments: hexadecimal bytes, legal origin, comma-separated chunk lengths.
procedure SHA256_Driver is
   package SHA renames CRDT.Security.SHA256;
   subtype Offset is Ada.Streams.Stream_Element_Offset;
   use type Offset;
   use type Ada.Streams.Stream_Element;

   Hex : constant String := Ada.Command_Line.Argument (1);
   Origin : constant Offset := Offset'Value (Ada.Command_Line.Argument (2));
   Chunks : constant String := Ada.Command_Line.Argument (3);
   N : constant Natural := Hex'Length / 2;
   --  For empty messages choose a legal, extreme null range. No huge array.
   First : constant Offset := (if N = 0 then Offset'Last else Origin);
   Last : constant Offset :=
     (if N = 0 then Offset'First else Origin + Offset (N - 1));
   Msg : SHA.Byte_Array (First .. Last);
   Empty : constant SHA.Byte_Array (Offset'Last .. Offset'First) :=
     (others => 0);
   Ctx : SHA.Context;
   D : SHA.Hash;
   Position : Natural := 0;
   Start : Positive := Chunks'First;

   function Nybble (C : Character) return SHA.Byte is
   begin
      case C is
         when '0' .. '9' => return Character'Pos (C) - Character'Pos ('0');
         when 'a' .. 'f' => return Character'Pos (C) - Character'Pos ('a') + 10;
         when others => raise Constraint_Error with "invalid hex";
      end case;
   end Nybble;

   procedure Print (Value : SHA.Hash) is
      Hex_Digits : constant String := "0123456789abcdef";
   begin
      for B of Value loop
         Ada.Text_IO.Put (Hex_Digits (Natural (B) / 16 + 1));
         Ada.Text_IO.Put (Hex_Digits (Natural (B) mod 16 + 1));
      end loop;
      Ada.Text_IO.New_Line;
   end Print;
begin
   if Hex'Length mod 2 /= 0 then
      raise Constraint_Error with "odd hex length";
   end if;
   for I in Msg'Range loop
      Msg (I) := Nybble (Hex (2 * Position + 1)) * 16
        + Nybble (Hex (2 * Position + 2));
      Position := Position + 1;
   end loop;
   SHA.Digest (Msg, D);
   Print (D);
   SHA.Init (Ctx);
   Position := 0;
   for J in Chunks'Range loop
      if Chunks (J) = ',' or else J = Chunks'Last then
         declare
            Finish : constant Natural :=
              (if Chunks (J) = ',' then J - 1 else J);
            Size : constant Natural := Natural'Value (Chunks (Start .. Finish));
         begin
            if Size > N - Position then
               raise Constraint_Error with "chunks exceed message";
            elsif Size = 0 then
               SHA.Update (Ctx, Empty);
               SHA.Update (Ctx, Msg (1 .. 0));
            else
               declare
                  Lo : constant Offset := Origin + Offset (Position);
                  Hi : constant Offset := Lo + Offset (Size - 1);
               begin
                  SHA.Update (Ctx, Msg (Lo .. Hi));
               end;
            end if;
            Position := Position + Size;
         end;
         Start := J + 1;
      end if;
   end loop;
   if Position /= N then
      raise Constraint_Error with "chunks do not cover message";
   end if;
   SHA.Final (Ctx, D);
   Print (D);
end SHA256_Driver;