--  Representation-independent client proof.
--
--  This unit may only use the visible abstraction of Fixed_Pool: the ghost
--  Free_Model, the Id_Sets instantiation and the public operations. It must
--  not depend on Free_Stack, Top, array indices, the representation
--  invariant or private helpers, and it must not rely on LIFO order.

with Fixed_Pool; use Fixed_Pool;

package Fixed_Pool_Client_Proof with SPARK_Mode is

   use type Fixed_Pool.Id_Sets.Set;

   procedure Two_Allocations_Then_Release (A, B : out Object_Id)
   with Global => null,
        Post   => A /= B;
   --  Initialize P; Allocate (P, A); Allocate (P, B); Release (P, A);
   --  proves in the body that A and B are distinct, both were allocated,
   --  A becomes free again and B stays allocated.

   procedure Round_Trip (P : in out Pool)
   with Global => null,
        Pre    => Free_Count (P) > 0,
        Post   => Free_Model (P) = Free_Model (P)'Old
                  and Free_Count (P) = Free_Count (P)'Old;
   --  Allocate then release the same identity on an arbitrary non-exhausted
   --  pool: the abstract free set is unchanged.

   procedure Release_Then_Allocate (P : in out Pool; Id : Object_Id)
   with Global => null,
        Pre    => Is_Allocated (P, Id),
        Post   => Free_Count (P) = Free_Count (P)'Old;
   --  After a release the pool is never exhausted, so Allocate's
   --  precondition holds; the identity it returns is not assumed to be Id.

end Fixed_Pool_Client_Proof;
