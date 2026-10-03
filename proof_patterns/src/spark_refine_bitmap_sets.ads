with SPARK.Big_Integers; use SPARK.Big_Integers;
with SPARK.Containers.Functional.Sets;

--  Task 019 experimental candidate. All operations are proof-only;
--  production retains its own checked modular mutations.
--  Version 1: ordinal offsets and storage extent fit in Integer. Words
--  have binary modulus 2**Bits_Per_Word, independently of physical Size.
generic
   type Element_Type is (<>);
   type Word_Type is mod <>;
   type Word_Index_Type is range <>;
   type Storage_Array is array (Word_Index_Type) of Word_Type;
   with package Element_Sets is new SPARK.Containers.Functional.Sets
     (Element_Type => Element_Type, Equivalent_Elements => "=", others => <>);
   Bits_Per_Word : Positive;
package SPARK_Refine_Bitmap_Sets with SPARK_Mode, Always_Terminates is
   pragma Compile_Time_Error
     (Word_Type'Modulus /= 2 ** Bits_Per_Word, "binary word modulus required");
   pragma Compile_Time_Error
     ((Word_Index_Type'Pos (Word_Index_Type'Last)
       - Word_Index_Type'Pos (Word_Index_Type'First) + 1) * Bits_Per_Word
      < Element_Type'Pos (Element_Type'Last)
        - Element_Type'Pos (Element_Type'First) + 1,
      "storage cannot hold identity universe");

   function Offset (E : Element_Type) return Natural is
     (Element_Type'Pos (E) - Element_Type'Pos (Element_Type'First))
   with Ghost;
   function Word_Index (E : Element_Type) return Word_Index_Type is
     (Word_Index_Type'Val
       (Word_Index_Type'Pos (Word_Index_Type'First) + Offset (E) / Bits_Per_Word))
   with Ghost;
   function Mask (E : Element_Type) return Word_Type is
     (2 ** (Offset (E) mod Bits_Per_Word))
   with Ghost;
   function Bit_Is_Set (Words : Storage_Array; E : Element_Type) return Boolean is
     ((Words (Word_Index (E)) and Mask (E)) /= 0)
   with Ghost;
   function Universe_Size return Big_Natural is
     (To_Big_Integer (Element_Type'Pos (Element_Type'Last)
                     - Element_Type'Pos (Element_Type'First) + 1))
   with Ghost;
   function Padding_Is_Canonical (Words : Storage_Array) return Boolean is
     (for all I in Word_Index_Type =>
       (for all B in 0 .. Bits_Per_Word - 1 =>
         (if (Word_Index_Type'Pos (I)
              - Word_Index_Type'Pos (Word_Index_Type'First)) * Bits_Per_Word + B
             > Offset (Element_Type'Last)
          then (Words (I) and 2 ** B) = 0)))
   with Ghost;
   function Model (Words : Storage_Array) return Element_Sets.Set
   with Ghost, Global => null,
        Post => (for all E in Element_Type =>
          Element_Sets.Contains (Model'Result, E) = Bit_Is_Set (Words, E))
          and Element_Sets.Length (Model'Result) <= Universe_Size
          and ((Element_Sets.Length (Model'Result) = Universe_Size)
            = (for all E in Element_Type => Bit_Is_Set (Words, E)))
          and ((Element_Sets.Length (Model'Result) = 0)
            = (for all E in Element_Type => not Bit_Is_Set (Words, E)));

   procedure Equal_Length (Left, Right : Element_Sets.Set)
   with Ghost, Global => null,
        Pre => Element_Sets."=" (Left, Right),
        Post => Element_Sets.Length (Left) = Element_Sets.Length (Right);

   procedure Lemma_Clear_Bit
     (Old_Words, New_Words : Storage_Array; E : Element_Type)
   with Ghost, Global => null,
        Pre => Bit_Is_Set (Old_Words, E)
          and New_Words = (Old_Words with delta
            Word_Index (E) => Old_Words (Word_Index (E)) and not Mask (E)),
        Post => Element_Sets."="
          (Model (New_Words), Element_Sets.Remove (Model (Old_Words), E))
          and Element_Sets.Length (Model (New_Words))
            = Element_Sets.Length (Model (Old_Words)) - 1
          and (if Padding_Is_Canonical (Old_Words)
               then Padding_Is_Canonical (New_Words));

   procedure Lemma_Set_Bit
     (Old_Words, New_Words : Storage_Array; E : Element_Type)
   with Ghost, Global => null,
        Pre => not Bit_Is_Set (Old_Words, E)
          and New_Words = (Old_Words with delta
            Word_Index (E) => Old_Words (Word_Index (E)) or Mask (E)),
        Post => Element_Sets."="
          (Model (New_Words), Element_Sets.Add (Model (Old_Words), E))
          and Element_Sets.Length (Model (New_Words))
            = Element_Sets.Length (Model (Old_Words)) + 1
          and (if Padding_Is_Canonical (Old_Words)
               then Padding_Is_Canonical (New_Words));
end SPARK_Refine_Bitmap_Sets;