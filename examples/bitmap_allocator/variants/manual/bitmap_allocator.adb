package body Bitmap_Allocator with SPARK_Mode is
   procedure Equal_Length (Left, Right : Id_Sets.Set)
   with Ghost, Pre => Left = Right,
        Post => Id_Sets.Length (Left) = Id_Sets.Length (Right)
   is
   begin
      pragma Assert (Id_Sets.Num_Overlaps (Left, Right) = Id_Sets.Length (Left));
   end Equal_Length;

   function Is_Free (P : Pool; Id : Object_Id) return Boolean is
     (Bitmap_Contains (P.Words, Id));

   function Free_Count (P : Pool) return Pool_Count is (P.Count);
   function Is_Exhausted (P : Pool) return Boolean is (P.Count = 0);

   function Free_Model (P : Pool) return Id_Sets.Set is
     (Bitmap_Model (P.Words));

   function Bitmap_Model (Words : Word_Array) return Id_Sets.Set is
      Result : Id_Sets.Set;
   begin
      for Id in Object_Id loop
         pragma Loop_Invariant
           (for all J in Object_Id => Id_Sets.Contains (Result, J)
             = (J < Id and then Bitmap_Contains (Words, J)));
         pragma Loop_Invariant (Id_Sets.Length (Result) <= To_Big_Integer (Id));
         pragma Loop_Invariant
           ((Id_Sets.Length (Result) = To_Big_Integer (Id))
             = (for all J in Object_Id'First .. Id - 1 => Bitmap_Contains (Words, J)));
         if Bitmap_Contains (Words, Id) then
            Result := Id_Sets.Add (Result, Id);
         end if;
      end loop;
      return Result;
   end Bitmap_Model;

   procedure Initialize (P : out Pool) is
   begin
      P := (Words => [0 => Interfaces.Unsigned_32'Last,
                     1 => Interfaces.Unsigned_32'Last,
                     2 => 2 ** 6 - 1],
            Count => Capacity);
   end Initialize;

   procedure Allocate (P : in out Pool; Id : out Object_Id) is
      Old_Model : constant Id_Sets.Set := Bitmap_Model (P.Words) with Ghost;
      Old_Words : constant Word_Array := P.Words with Ghost;
   begin
      Id := Object_Id'First;
      for Candidate in Object_Id loop
         pragma Loop_Invariant
           (for all J in Object_Id'First .. Candidate - 1 => not Bitmap_Contains (P.Words, J));
         if Is_Free (P, Candidate) then
            Id := Candidate;
            P.Words (Natural (Id) / 32) :=
              P.Words (Natural (Id) / 32) and not Mask (Id);
            P.Count := P.Count - 1;
            pragma Assert
              (for all J in Object_Id => Bitmap_Contains (P.Words, J)
                = (J /= Id and then Bitmap_Contains (Old_Words, J)));
            Equal_Length (Bitmap_Model (P.Words), Id_Sets.Remove (Old_Model, Id));
            return;
         end if;
      end loop;
   end Allocate;

   procedure Release (P : in out Pool; Id : Object_Id) is
      Old_Model : constant Id_Sets.Set := Bitmap_Model (P.Words) with Ghost;
      Old_Words : constant Word_Array := P.Words with Ghost;
   begin
      P.Words (Natural (Id) / 32) :=
        P.Words (Natural (Id) / 32) or Mask (Id);
      pragma Assert
        (for all J in Object_Id => Bitmap_Contains (P.Words, J)
          = (J = Id or else Bitmap_Contains (Old_Words, J)));
      Equal_Length (Bitmap_Model (P.Words), Id_Sets.Add (Old_Model, Id));
      P.Count := P.Count + 1;
   end Release;
end Bitmap_Allocator;